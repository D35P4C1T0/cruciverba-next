import pytest
import sqlite3
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as cruciverba_app
from cruciverba.config import get_form_password, get_admin_password
from cruciverba.database import get_db_connection
from cruciverba.validation import sanitize_csv_cell, sanitize_input, is_valid_word, is_valid_clue

# Global test database
test_db_path = None

@pytest.fixture(scope="session")
def test_database():
    """Create a temporary database for the entire test session."""
    global test_db_path
    fd, test_db_path = tempfile.mkstemp()
    os.close(fd)
    
    # Initialize the database with the table
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parola TEXT NOT NULL,
            frase_indizio TEXT NOT NULL,
            nome TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    
    yield test_db_path
    
    # Cleanup
    os.unlink(test_db_path)

@pytest.fixture
def client(test_database, monkeypatch):
    """Use the real database layer with a temporary database and isolated settings."""
    monkeypatch.setitem(cruciverba_app.config, 'TESTING', True)
    monkeypatch.setitem(cruciverba_app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setitem(cruciverba_app.config, 'DATABASE_PATH', test_database)
    limiter = cruciverba_app.extensions['rate_limiter']
    monkeypatch.setattr(limiter, 'enabled', False)

    with cruciverba_app.test_client() as client:
        with cruciverba_app.app_context():
            yield client

@pytest.fixture
def authenticated_session(client):
    """Create an authenticated session for form access."""
    with client.session_transaction() as sess:
        sess['form_access'] = True
    return client

@pytest.fixture
def admin_session(client):
    """Create an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    return client

class TestSecurityHeaders:
    """Test security headers and configurations."""
    
    def test_security_headers_present(self, client):
        """Test that security headers are present."""
        response = client.get('/')
        
        # Test for security headers
        assert 'X-Content-Type-Options' in response.headers
        assert 'X-Frame-Options' in response.headers
        assert response.headers['X-XSS-Protection'] == '0'
        assert 'Strict-Transport-Security' not in response.headers
        assert response.headers['Referrer-Policy'] == 'same-origin'
        assert 'Permissions-Policy' in response.headers
        assert response.headers['Cache-Control'] == 'no-store'
        
        # Test CSP header
        assert 'Content-Security-Policy' in response.headers
        assert "object-src 'none'" in response.headers['Content-Security-Policy']
        assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    
    def test_session_cookie_security(self, client):
        """Test session cookie security settings."""
        with client.session_transaction() as sess:
            # Test that we can access session (indicates cookies work)
            sess['test'] = 'value'
        
        # Test that session persists
        with client.session_transaction() as sess:
            assert sess.get('test') == 'value'

class TestAuthentication:
    """Test authentication mechanisms."""
    
    def test_form_access_requires_password(self, client):
        """Test that form access requires password."""
        response = client.get('/')
        assert response.status_code == 200
        assert 'Password' in response.get_data(as_text=True)
    
    def test_form_login_success(self, client):
        """Test successful form login."""
        response = client.post('/', data={'access_password': get_form_password()})
        # Should redirect or show form page
        assert response.status_code in [200, 302]
    
    def test_form_login_failure(self, client):
        """Test failed form login."""
        response = client.post('/', data={'access_password': 'wrong_password'})
        assert response.status_code == 200
        assert 'Password errata' in response.get_data(as_text=True)
    
    def test_admin_login_success(self, client):
        """Test successful admin login."""
        response = client.post('/admin', data={'password': get_admin_password()})
        assert response.status_code in [200, 302]  # Success or redirect
    
    def test_admin_login_failure(self, client):
        """Test failed admin login."""
        response = client.post('/admin', data={'password': 'wrong_password'})
        assert response.status_code == 200
        assert 'Password errata' in response.get_data(as_text=True)
    
    def test_form_logout(self, authenticated_session):
        """Test form logout functionality."""
        # Access logout
        response = authenticated_session.post('/logout')
        assert response.status_code == 302  # Should redirect
        
        # Verify we're logged out by trying to access form
        response = authenticated_session.get('/')
        assert 'Password' in response.get_data(as_text=True)
    
    def test_admin_logout(self, admin_session):
        """Test admin logout functionality."""
        response = admin_session.post('/admin/logout')
        assert response.status_code == 302  # Should redirect

    def test_logout_rejects_get(self, authenticated_session, admin_session):
        assert authenticated_session.get('/logout').status_code == 405
        assert admin_session.get('/admin/logout').status_code == 405

class TestFormSubmission:
    """Test form submission functionality."""
    
    def test_valid_submission(self, authenticated_session):
        """Test valid form submission."""
        data = {
            'parola': 'AMORE',
            'frase_indizio': 'Sentimento che prova per il futuro marito',
            'nome': 'Maria'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        
        # Should show success page with user's name
        page_content = response.get_data(as_text=True)
        assert 'Grazie Maria!' in page_content
    
    def test_missing_required_fields(self, authenticated_session):
        """Test submission with missing required fields."""
        # Missing parola
        data = {
            'frase_indizio': 'Una frase indizio molto lunga per test',
            'nome': 'Test'
        }
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        
        # Missing frase_indizio
        data = {
            'parola': 'TEST',
            'nome': 'Test'
        }
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        
        # Both missing (nome is optional)
        data = {
            'nome': 'Test'
        }
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
    
    def test_word_accepts_numbers_and_symbols(self, authenticated_session):
        """Words may contain numbers, punctuation, and symbols."""
        data = {
            'parola': 'TEST123!@#',
            'frase_indizio': 'Una frase indizio abbastanza lunga',
            'nome': 'Test'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        page_content = response.get_data(as_text=True)
        assert 'Grazie Test!' in page_content
    
    def test_short_clue_is_accepted(self, authenticated_session):
        """A clue containing one or more characters is accepted."""
        data = {
            'parola': 'TEST',
            'frase_indizio': 'X',
            'nome': 'Test'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        page_content = response.get_data(as_text=True)
        assert 'Grazie Test!' in page_content
    
    def test_duplicate_submission_is_allowed(self, authenticated_session):
        """The same contribution may be submitted more than once."""
        data = {
            'parola': 'DUPLICATE',
            'frase_indizio': 'Una frase indizio molto lunga per evitare errori',
            'nome': 'Test User'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        assert 'Grazie Test User!' in response.get_data(as_text=True)
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        assert 'Grazie Test User!' in response.get_data(as_text=True)

        conn = get_db_connection()
        count = conn.execute(
            'SELECT COUNT(*) FROM submissions WHERE parola = ? AND frase_indizio = ?',
            ('duplicate', data['frase_indizio'])
        ).fetchone()[0]
        conn.close()
        assert count == 2
    
class TestInputSanitization:
    """Test input sanitization and XSS prevention."""
    
    def test_xss_prevention_in_parola(self, authenticated_session):
        """Test XSS prevention in parola field."""
        data = {
            'parola': '<script>alert("xss")</script>TEST',
            'frase_indizio': 'Una frase indizio molto lunga per test XSS',
            'nome': 'Test'
        }
        
        response = authenticated_session.post('/', data=data)
        page_content = response.get_data(as_text=True)
        # Check that malicious script content is not present in user data areas
        assert 'alert("xss")' not in page_content
    
    def test_xss_prevention_in_frase_indizio(self, authenticated_session):
        """Test XSS prevention in frase_indizio field."""
        data = {
            'parola': 'TEST',
            'frase_indizio': '<script>alert("xss")</script>Una frase indizio molto lunga',
            'nome': 'Test'
        }
        
        response = authenticated_session.post('/', data=data)
        page_content = response.get_data(as_text=True)
        # Check that malicious script content is not present in user data areas
        assert 'alert("xss")' not in page_content
    
    def test_xss_prevention_in_nome(self, authenticated_session):
        """Test XSS prevention in nome field."""
        data = {
            'parola': 'TEST',
            'frase_indizio': 'Una frase indizio molto lunga per test',
            'nome': '<script>alert("xss")</script>TestUser'
        }
        
        response = authenticated_session.post('/', data=data)
        page_content = response.get_data(as_text=True)
        # Check that malicious script content is not present in user data areas
        assert 'alert("xss")' not in page_content

class TestAdminFunctionality:
    """Test admin panel functionality."""
    
    def test_admin_dashboard_access(self, admin_session):
        """Test admin dashboard access with authentication."""
        response = admin_session.get('/admin')
        assert response.status_code == 200
        assert 'Pannello Amministratore' in response.get_data(as_text=True)
    
    def test_admin_dashboard_without_auth(self, client):
        """Test admin dashboard access without authentication."""
        response = client.get('/admin')
        assert response.status_code == 200
        assert 'Password' in response.get_data(as_text=True)
    
    def test_csv_export_with_auth(self, admin_session):
        """Test CSV export with authentication."""
        response = admin_session.get('/admin/export')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
    
    def test_csv_export_without_auth(self, client):
        """Test CSV export without authentication."""
        response = client.get('/admin/export')
        assert response.status_code == 403
    
    def test_delete_submission_with_auth(self, admin_session):
        """Test submission deletion with authentication."""
        # First create a submission to delete
        conn = get_db_connection()
        conn.execute('INSERT INTO submissions (parola, frase_indizio, nome) VALUES (?, ?, ?)',
                    ('testdelete', 'test indizio abbastanza lungo', 'Test User'))
        conn.commit()
        
        # Get the submission ID
        submission = conn.execute('SELECT id FROM submissions WHERE parola = ?', ('testdelete',)).fetchone()
        submission_id = submission['id']
        conn.close()
        
        # Test deletion
        response = admin_session.post(f'/admin/delete/{submission_id}')
        assert response.status_code == 302  # Should redirect with error message
    
    def test_delete_nonexistent_submission(self, admin_session):
        """Test deletion of non-existent submission."""
        response = admin_session.post('/admin/delete/99999')
        assert response.status_code == 302  # Should redirect with error message

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiting_configured(self, client):
        """Test that rate limiting is properly configured."""
        # Verify that the limiter is being used (registered on the application)
        limiter = cruciverba_app.extensions['rate_limiter']
        assert limiter is not None
        
        # In actual deployment, rate limiting would work
        # In tests, we disable it for easier testing

class TestDatabaseOperations:
    """Test database operations."""
    
    def test_database_initialization(self):
        """Test database initialization."""
        # Create temporary database
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        
        # Test table creation
        conn.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parola TEXT NOT NULL,
                frase_indizio TEXT NOT NULL,
                nome TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Verify table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='submissions'")
        assert cursor.fetchone() is not None
        conn.close()
    
    def test_submission_storage(self, authenticated_session):
        """Test that submissions are properly stored in database."""
        # Use a unique word for this test
        data = {
            'parola': 'FELICITA',
            'frase_indizio': 'Stato d\'animo sempre presente in lei con questa emozione',
            'nome': 'Test Storage User'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        assert 'Grazie Test Storage User!' in response.get_data(as_text=True)
        
        # Verify in database (words are stored in lowercase)
        conn = get_db_connection()
        submission = conn.execute('SELECT * FROM submissions WHERE parola = ? AND nome = ?', 
                                 ('felicita', 'Test Storage User')).fetchone()
        assert submission is not None
        assert submission['parola'] == 'felicita'
        assert submission['nome'] == 'Test Storage User'
        assert 'Stato d\'animo sempre presente' in submission['frase_indizio']
        conn.close()

class TestSuccessPage:
    """Test success page and add another word functionality."""
    
    def test_success_page_display(self, authenticated_session):
        """Test success page displays correctly after submission."""
        data = {
            'parola': 'GIOIA',
            'frase_indizio': 'Sentimento che trasmette sempre',
            'nome': 'Mario Rossi'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        
        # Check success page elements
        page_content = response.get_data(as_text=True)
        assert 'Grazie Mario Rossi!' in page_content
        assert 'Aggiungi un\'altra parola' in page_content
        assert 'Finito, disconnetti' in page_content
        assert 'intro-copy' not in page_content
    
    def test_add_another_word_link(self, authenticated_session):
        """Test that add another word link works."""
        # First submission
        data = {
            'parola': 'SORRISO',
            'frase_indizio': 'Espressione sempre presente sul suo volto',
            'nome': 'Mario Rossi'
        }
        
        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200
        
        # Check that we can access the form again
        response = authenticated_session.get('/')
        assert response.status_code == 200
        assert 'Parola' in response.get_data(as_text=True)

    def test_add_another_word_keeps_name_and_clears_fields(self, authenticated_session):
        """A consecutive contribution keeps only the contributor name."""
        data = {
            'parola': 'RICORDO',
            'frase_indizio': 'Un momento speciale passato insieme tanti anni fa',
            'nome': 'Luca Bianchi'
        }

        response = authenticated_session.post('/', data=data)
        assert response.status_code == 200

        response = authenticated_session.get('/nuovo-contributo', follow_redirects=True)
        page_content = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'value="Luca Bianchi"' in page_content
        assert 'value="RICORDO"' not in page_content
        assert 'Un momento speciale passato insieme tanti anni fa' not in page_content

    def test_logout_clears_contributor_name(self, authenticated_session):
        """Logging out removes the remembered contributor name."""
        with authenticated_session.session_transaction() as session_data:
            session_data['contributor_name'] = 'Luca Bianchi'

        authenticated_session.post('/logout')

        with authenticated_session.session_transaction() as session_data:
            assert 'contributor_name' not in session_data

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_404_handling(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent-page')
        assert response.status_code == 404
    
    def test_csrf_error_handling(self, client):
        """Test CSRF error handling."""
        # This would need CSRF enabled and proper token testing
        # For now, verify that CSRF protection exists (registered on the application)
        csrf = cruciverba_app.extensions['csrf']
        assert csrf is not None
    
    def test_invalid_submission_id(self, admin_session):
        """Test handling of invalid submission ID."""
        response = admin_session.post('/admin/delete/invalid')
        assert response.status_code == 404

class TestConfigurationAndEnvironment:
    """Test configuration and environment variables."""
    
    def test_environment_variables(self):
        """Test environment variable handling."""
        # Test password functions
        assert callable(get_form_password)
        assert callable(get_admin_password)
        
        # Test default values
        form_password = get_form_password()
        admin_password = get_admin_password()
        
        assert isinstance(form_password, str)
        assert isinstance(admin_password, str)
        assert len(form_password) > 0
        assert len(admin_password) > 0

class TestSecurityFunctions:
    """Test security utility functions."""
    
    def test_sanitize_input(self):
        """Test input sanitization function."""
        # Test HTML removal
        dirty_input = '<script>alert("xss")</script>Hello'
        clean_input = sanitize_input(dirty_input)
        assert '<script>' not in clean_input
        assert 'Hello' in clean_input
        
        # Test normal text
        normal_input = 'Normal text input'
        clean_input = sanitize_input(normal_input)
        assert clean_input == normal_input
        
        # Test empty input
        empty_input = ''
        clean_input = sanitize_input(empty_input)
        assert clean_input == ''

        # Unsafe control characters are removed.
        assert sanitize_input('Test\x00Word') == 'TestWord'

    def test_csv_formula_sanitization(self):
        """Spreadsheet formula prefixes are exported as plain text."""
        assert sanitize_csv_cell('=SUM(1,1)') == "'=SUM(1,1)"
        assert sanitize_csv_cell('+123') == "'+123"
        assert sanitize_csv_cell('normal text') == 'normal text'
    
    def test_validation_functions(self):
        """Test validation utility functions."""
        # Test word validation
        assert is_valid_word('HELLO')
        assert is_valid_word('hello')
        assert is_valid_word('Hello World')
        assert is_valid_word('Hello123')
        assert is_valid_word('Hello!')
        assert is_valid_word('🎓 2026')
        assert not is_valid_word('   ')
        
        # Test clue validation
        assert is_valid_clue('This is a long enough clue')
        assert is_valid_clue('X')
        assert not is_valid_clue('   ')

class TestAccessControl:
    """Test access control and permissions."""
    
    def test_form_access_without_auth(self, client):
        """Test that form access requires authentication."""
        response = client.get('/')
        page_content = response.get_data(as_text=True)
        
        # Should show password form, not submission form (unless rate limited)
        if response.status_code == 200:
            assert 'Password' in page_content or 'access_password' in page_content
        elif response.status_code == 429:
            # Rate limited - this is also acceptable
            assert 'troppi tentativi' in page_content.lower() or 'too many' in page_content.lower()
    
    def test_admin_functions_without_auth(self, client):
        """Test that admin functions require authentication."""
        # Admin dashboard
        response = client.get('/admin')
        assert 'Password' in response.get_data(as_text=True)
        
        # CSV export
        response = client.get('/admin/export')
        assert response.status_code == 403
        
        # Delete submission
        response = client.post('/admin/delete/1')
        assert response.status_code == 403


class TestProductionHardening:
    def test_weak_passwords_require_explicit_override(self, monkeypatch):
        from cruciverba.config import validate_production_config

        production_environment = {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'FORM_PASSWORD': 'corta',
            'ADMIN_PASSWORD': 'breve',
            'FORCE_HTTPS': 'True',
            'TRUSTED_HOSTS': 'cruciverba.example.it',
        }
        for name, value in production_environment.items():
            monkeypatch.setenv(name, value)
        monkeypatch.delenv('FORM_PASSWORD_HASH', raising=False)
        monkeypatch.delenv('ADMIN_PASSWORD_HASH', raising=False)
        monkeypatch.delenv('ALLOW_WEAK_PASSWORDS', raising=False)

        with pytest.raises(RuntimeError, match='ALLOW_WEAK_PASSWORDS=True'):
            validate_production_config()

        monkeypatch.setenv('ALLOW_WEAK_PASSWORDS', 'True')
        validate_production_config()

    def test_healthcheck(self, client):
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.get_json() == {'status': 'ok'}

    def test_https_csrf_accepts_same_origin_referrer(self, client):
        import re

        original_csrf_setting = cruciverba_app.config['WTF_CSRF_ENABLED']
        cruciverba_app.config['WTF_CSRF_ENABLED'] = True
        try:
            login_page = client.get('/', base_url='https://localhost')
            token_match = re.search(
                r'name="csrf_token"[^>]*value="([^"]+)"',
                login_page.get_data(as_text=True),
            )
            assert token_match

            response = client.post(
                '/',
                base_url='https://localhost',
                headers={'Referer': 'https://localhost/'},
                data={
                    'csrf_token': token_match.group(1),
                    'access_password': get_form_password(),
                },
            )
        finally:
            cruciverba_app.config['WTF_CSRF_ENABLED'] = original_csrf_setting

        assert response.status_code == 302
        assert response.headers['Referrer-Policy'] == 'same-origin'

    def test_untrusted_host_is_rejected(self, client):
        original_hosts = cruciverba_app.config['TRUSTED_HOSTS']
        cruciverba_app.config['TRUSTED_HOSTS'] = ['localhost']
        try:
            response = client.get('/', headers={'Host': 'evil.example'})
        finally:
            cruciverba_app.config['TRUSTED_HOSTS'] = original_hosts
        assert response.status_code == 400
        assert 'Richiesta non valida' in response.get_data(as_text=True)

    def test_oversized_request_is_rejected(self, authenticated_session):
        response = authenticated_session.post(
            '/',
            data={'parola': 'X' * 17000, 'frase_indizio': 'X', 'nome': 'Test'},
        )
        assert response.status_code == 413

    def test_honeypot_does_not_store_submission(self, authenticated_session):

        with get_db_connection() as connection:
            count_before = connection.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]

        response = authenticated_session.post(
            '/',
            data={
                'parola': 'BOT',
                'frase_indizio': 'X',
                'nome': 'Bot',
                'website': 'https://spam.example',
            },
        )

        with get_db_connection() as connection:
            count_after = connection.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]

        assert response.status_code == 302
        assert count_after == count_before

    def test_hsts_only_on_secure_requests(self, client, monkeypatch):

        monkeypatch.setitem(cruciverba_app.config, 'SESSION_COOKIE_SECURE', True)
        response = client.get('/healthz', base_url='https://localhost')
        assert response.headers['Strict-Transport-Security'] == 'max-age=31536000'


class TestLeanRateLimiting:
    @pytest.fixture
    def limited_client(self, client, monkeypatch):
        limiter = cruciverba_app.extensions['rate_limiter']

        monkeypatch.setenv('RATE_LIMIT_DEFAULT', '120 per minute')
        monkeypatch.setenv('RATE_LIMIT_LOGIN', '10 per minute')
        limiter.storage.reset()
        limiter.enabled = True
        yield client
        limiter.storage.reset()

    @pytest.mark.parametrize('path,field', [('/', 'access_password'), ('/admin', 'password')])
    def test_failed_password_attempts_are_limited(self, limited_client, path, field):
        for _ in range(10):
            assert limited_client.post(path, data={field: 'wrong'}).status_code == 200
        assert limited_client.post(path, data={field: 'wrong'}).status_code == 429

    @pytest.mark.parametrize('path,field,password', [
        ('/', 'access_password', get_form_password),
        ('/admin', 'password', get_admin_password),
    ])
    def test_successful_logins_do_not_consume_failure_quota(
        self, limited_client, path, field, password,
    ):
        for _ in range(12):
            assert limited_client.post(path, data={field: password()}).status_code == 302
        assert limited_client.post(path, data={field: 'wrong'}).status_code == 200

    def test_contributions_do_not_consume_login_quota(self, limited_client):
        with limited_client.session_transaction() as session:
            session['form_access'] = True
        for _ in range(12):
            # Invalid contribution renders the form; it is still not a password attempt.
            assert limited_client.post('/', data={'parola': ''}).status_code == 200
        assert limited_client.post('/', data={'access_password': 'wrong'}).status_code == 200

    def test_general_limit_is_configurable_and_health_is_exempt(self, limited_client, monkeypatch):
        monkeypatch.setenv('RATE_LIMIT_DEFAULT', '3 per minute')
        for _ in range(3):
            assert limited_client.get('/').status_code == 200
        assert limited_client.get('/').status_code == 429
        for _ in range(4):
            assert limited_client.get('/healthz').status_code == 200


class TestLeanDeployment:
    def test_production_accepts_memory_storage_with_valid_secrets(self, monkeypatch):
        from cruciverba.config import validate_production_config

        for name, value in {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'FORM_PASSWORD': 'strong-guest-password',
            'ADMIN_PASSWORD': 'strong-admin-password',
            'FORCE_HTTPS': 'True',
            'TRUSTED_HOSTS': 'cruciverba.example.it',
        }.items():
            monkeypatch.setenv(name, value)
        validate_production_config()

    def test_gunicorn_requires_one_worker_for_memory_rate_limiting(self, monkeypatch):
        import runpy
        from pathlib import Path
        from types import SimpleNamespace

        monkeypatch.setenv('WEB_CONCURRENCY', '2')
        monkeypatch.setenv('GUNICORN_THREADS', '4')
        config = runpy.run_path(str(Path(__file__).with_name('gunicorn.conf.py')))
        assert config['workers'] == 1
        assert config['threads'] == 4
        start = config['on_starting']
        start(SimpleNamespace(cfg=SimpleNamespace(workers=1)))
        with pytest.raises(RuntimeError, match='un solo worker'):
            start(SimpleNamespace(cfg=SimpleNamespace(workers=2)))


class TestApplicationFactory:
    def test_apps_keep_database_sessions_and_settings_separate(self, tmp_path, monkeypatch):
        from cruciverba import create_app
        from cruciverba.database import add_submission, init_db, list_submissions

        monkeypatch.setenv('APP_ENV', 'testing')
        monkeypatch.setenv('FORCE_HTTPS', 'False')
        monkeypatch.setenv('TRUSTED_PROXY_COUNT', '0')
        settings = {
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'RATELIMIT_ENABLED': False,
            'TRUSTED_HOSTS': ['localhost'],
        }
        first = create_app(dict(settings, SECRET_KEY='first-secret', DATABASE_PATH=str(tmp_path / 'first.db')))
        second = create_app(dict(settings, SECRET_KEY='second-secret', DATABASE_PATH=str(tmp_path / 'second.db')))

        with first.app_context():
            init_db()
            add_submission('ciao', 'Un saluto', 'Mario')
            assert len(list_submissions()) == 1
        with second.app_context():
            init_db()
            assert list_submissions() == []

        assert first.extensions['rate_limiter'] is not second.extensions['rate_limiter']
        assert first.extensions['csrf'] is not second.extensions['csrf']
        first_client = first.test_client()
        second_client = second.test_client()
        assert first_client.post('/', data={'access_password': get_form_password()}).status_code == 302
        cookie = first_client.get_cookie('cruciverba_session')
        second_client.set_cookie('cruciverba_session', cookie.value)
        assert 'Password di accesso' in second_client.get('/').get_data(as_text=True)
        with first_client.session_transaction() as session:
            assert session['form_access']
        assert first_client.get('/static/css/app.css').status_code == 200

    def test_app_limiters_do_not_share_request_counters(self, monkeypatch):
        from cruciverba import create_app

        monkeypatch.setenv('APP_ENV', 'testing')
        monkeypatch.setenv('RATE_LIMIT_DEFAULT', '1 per minute')
        settings = {'TESTING': True, 'RATELIMIT_ENABLED': True, 'TRUSTED_HOSTS': ['localhost']}
        first = create_app(settings).test_client()
        second = create_app(settings).test_client()
        assert first.get('/').status_code == 200
        assert first.get('/').status_code == 429
        assert second.get('/').status_code == 200


class TestPdfDownloads:
    @pytest.mark.parametrize('authenticated', [False, True])
    def test_pdf_requires_organizer_access(self, client, authenticated):
        if authenticated:
            with client.session_transaction() as session:
                session['form_access'] = True
        assert client.get('/admin/export/pdf').status_code == 403

    def test_dashboard_offers_pdf_and_csv(self, admin_session):
        page = admin_session.get('/admin').get_data(as_text=True)
        assert 'Scarica PDF' in page and '/admin/export/pdf' in page
        assert 'Esporta CSV' in page and 'href="/admin/export"' in page

    def test_pdf_download_contains_contribution_and_private_headers(self, admin_session, monkeypatch):
        import io
        from pypdf import PdfReader

        monkeypatch.setenv('CELEBRATED_PERSON_NAME', 'Èrica')
        with get_db_connection() as connection:
            connection.execute(
                'INSERT INTO submissions (parola, frase_indizio, nome, timestamp) VALUES (?, ?, ?, ?)',
                ('caffè', 'È ciò che dà energia: <b>caffè</b> & tè.', 'Zoë', '2026-10-11 12:30:00'),
            )
        response = admin_session.get('/admin/export/pdf')
        assert response.status_code == 200
        assert response.mimetype == 'application/pdf'
        assert response.headers['Content-Disposition'] == 'attachment; filename=cruciverba_rica.pdf'
        assert response.headers['Cache-Control'] == 'no-store'
        reader = PdfReader(io.BytesIO(response.data))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        assert 'Cruciverba di Èrica' in text
        assert 'CAFFÈ' in text and 'Zoë' in text
        assert '<b>caffè</b> & tè.' in text
        assert '11/10/2026 alle 12:30' in text
        # The original CSV remains downloadable alongside the document.
        assert admin_session.get('/admin/export').mimetype == 'text/csv'

    @pytest.mark.parametrize('count', [0, 1, 45])
    def test_empty_and_multipage_documents_preserve_all_entries(self, count):
        import io
        from pypdf import PdfReader
        from cruciverba.exports import create_pdf_bytes

        submissions = [
            {
                'parola': f'PAROLA{number:03d}' + 'X' * 40,
                'frase_indizio': 'Un indizio più lungo, con accenti e simboli < & >. ' * 4,
                'nome': None,
                'timestamp': '2026-10-11 12:30:00',
            }
            for number in range(count)
        ]
        reader = PdfReader(io.BytesIO(create_pdf_bytes(submissions, 'Bianca')))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        assert len(reader.pages) >= 1
        if count == 0:
            assert 'Nessun contributo ancora' in text
        for number in range(count):
            assert f'PAROLA{number:03d}' in text
        if count:
            assert 'Anonimo' in text
        if count == 45:
            assert len(reader.pages) > 1
        for number, page in enumerate(reader.pages, start=1):
            assert f'Pagina {number}' in page.extract_text()
