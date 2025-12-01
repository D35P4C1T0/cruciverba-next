import sqlite3
import csv
import os
import secrets
import logging
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, session, abort
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wtforms import StringField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Length
import bleach
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Security Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour CSRF token validity
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FORCE_HTTPS', 'False').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Initialize security extensions
csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv('RATE_LIMIT_STORAGE_URL', 'memory://')
)

# Configure logging
log_handlers = [logging.StreamHandler()]
# Only add file handler if we can write to filesystem
try:
    log_handlers.append(logging.FileHandler('/tmp/app.log'))
except (OSError, PermissionError):
    pass  # Use only StreamHandler if we can't write files

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# WTF Forms for CSRF protection
class LoginForm(FlaskForm):
    access_password = PasswordField('Password', validators=[DataRequired()])

class AdminLoginForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])

class ContributionForm(FlaskForm):
    parola = StringField('Parola', validators=[
        DataRequired(message="La parola è obbligatoria"),
        Length(min=1, max=50, message="La parola deve essere tra 1 e 50 caratteri")
    ])
    frase_indizio = TextAreaField('Frase indizio', validators=[
        DataRequired(message="La frase indizio è obbligatoria"),
        Length(min=10, max=200, message="La frase indizio deve essere tra 10 e 200 caratteri")
    ])
    nome = StringField('Nome', validators=[
        DataRequired(message="Il nome è obbligatorio"),
        Length(min=1, max=50, message="Il nome deve essere tra 1 e 50 caratteri")
    ])

# Security functions
def sanitize_input(text):
    """Sanitize user input to prevent XSS"""
    if not text:
        return text
    return bleach.clean(text.strip(), tags=[], attributes={}, strip=True)

def get_form_password():
    """Get form password from environment"""
    return os.getenv('FORM_PASSWORD', 'bianca')

def get_admin_password():
    """Get admin password from environment"""
    return os.getenv('ADMIN_PASSWORD', 'bianca2024')

def get_celebrated_person_name():
    """Get celebrated person name from environment"""
    return os.getenv('CELEBRATED_PERSON_NAME', 'Bianca')

def log_security_event(event_type, details):
    """Log security events"""
    client_ip = get_remote_address()
    logger.warning(f"SECURITY EVENT: {event_type} from {client_ip} - {details}")

# Database setup
def init_db():
    """Initialize database with proper path handling"""
    db_path = os.getenv('DATABASE_PATH', 'data/cruciverba.db')
    # Ensure data directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS submissions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  parola TEXT NOT NULL,
                  frase_indizio TEXT NOT NULL,
                  nome TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_db_connection():
    db_path = os.getenv('DATABASE_PATH', 'data/cruciverba.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys and other security features
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn

# Validation functions
def is_valid_word(word):
    """Check if input is a valid word (can contain spaces)"""
    return bool(re.match(r'^[a-zA-ZàáèéìíòóùúÀÁÈÉÌÍÒÓÙÚ\s]+$', word.strip()))

def is_valid_clue(clue):
    """Check if clue is at least 10 characters"""
    return len(clue.strip()) >= 10

# Security headers
@app.after_request
def set_security_headers(response):
    """Set security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Error handlers
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    log_security_event("CSRF_ERROR", f"Description: {e.description}")
    flash("Errore di sicurezza. Riprova.", 'error')
    return redirect(url_for('index')), 400

# Make function available to templates
@app.context_processor
def inject_person_name():
    """Make person name available to all templates"""
    return {'person_name': get_celebrated_person_name()}

@app.errorhandler(429)
def ratelimit_handler(e):
    log_security_event("RATE_LIMIT_EXCEEDED", f"Description: {e.description}")
    return render_template('error.html', 
                         title="Troppi tentativi",
                         message="Hai effettuato troppi tentativi. Riprova più tardi.",
                         person_name=get_celebrated_person_name()), 429

# Routes
@app.route('/', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def index():
    # Check if user provided the password for form access
    if request.method == 'POST':
        # Check if this is a password submission
        if 'access_password' in request.form:
            form = LoginForm()
            if form.validate_on_submit():
                password = sanitize_input(form.access_password.data)
                if password == get_form_password():
                    session['form_access'] = True
                    session.permanent = True
                    logger.info(f"Successful form login from {get_remote_address()}")
                    return redirect(url_for('index'))
                else:
                    log_security_event("INVALID_FORM_PASSWORD", f"Attempted password: {password[:3]}***")
                    flash("Password errata. Chiedi la password agli organizzatori!", 'error')
            return render_template('form_login.html', form=form, person_name=get_celebrated_person_name())
        
        # If not authenticated, redirect to password page
        if not session.get('form_access'):
            return redirect(url_for('index'))
        
        # Handle form submission (existing code)
        form = ContributionForm()
        if form.validate_on_submit():
            # Sanitize all inputs
            parola = sanitize_input(form.parola.data)
            frase_indizio = sanitize_input(form.frase_indizio.data)
            nome = sanitize_input(form.nome.data)
            
            # Additional validation
            if not is_valid_word(parola):
                flash("La parola può contenere solo lettere e spazi", 'error')
                return render_template('index.html', form=form)
            
            if not is_valid_clue(frase_indizio):
                flash("La frase indizio deve essere di almeno 10 caratteri", 'error')
                return render_template('index.html', form=form)
            
            # Check for duplicates (simple anti-spam)
            conn = get_db_connection()
            existing = conn.execute('SELECT * FROM submissions WHERE parola = ? AND frase_indizio = ?', 
                                   (parola.lower(), frase_indizio)).fetchone()
            if existing:
                flash("Questo contributo è già stato registrato", 'error')
                conn.close()
                return render_template('index.html', form=form)
            
            # Save to database with parameterized query (SQL injection protection)
            conn.execute('INSERT INTO submissions (parola, frase_indizio, nome) VALUES (?, ?, ?)',
                        (parola.lower(), frase_indizio, nome))
            conn.commit()
            conn.close()
            
            logger.info(f"New contribution from {get_remote_address()}: {parola[:10]}...")
            flash("Grazie! Il tuo contributo è stato registrato.", 'success')
            return render_template('success.html', nome=nome, person_name=get_celebrated_person_name())
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
    
    # If not authenticated, show password page
    if not session.get('form_access'):
        form = LoginForm()
        return render_template('form_login.html', form=form, person_name=get_celebrated_person_name())
    
    form = ContributionForm()
    return render_template('index.html', form=form, person_name=get_celebrated_person_name())

@app.route('/admin', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def admin():
    if request.method == 'POST':
        form = AdminLoginForm()
        if form.validate_on_submit():
            password = sanitize_input(form.password.data)
            if password == get_admin_password():
                session['admin_logged_in'] = True
                session.permanent = True
                logger.info(f"Successful admin login from {get_remote_address()}")
                return redirect(url_for('admin'))
            else:
                log_security_event("INVALID_ADMIN_PASSWORD", f"Attempted password: {password[:3]}***")
                flash("Password errata", 'error')
        return render_template('admin_login.html', form=form, person_name=get_celebrated_person_name())
    
    if not session.get('admin_logged_in'):
        form = AdminLoginForm()
        return render_template('admin_login.html', form=form, person_name=get_celebrated_person_name())
    
    conn = get_db_connection()
    submissions = conn.execute('SELECT * FROM submissions ORDER BY timestamp DESC').fetchall()
    conn.close()
    
    return render_template('admin.html', submissions=submissions, person_name=get_celebrated_person_name())

@app.route('/admin/export')
@limiter.limit("10 per minute")
def export_csv():
    if not session.get('admin_logged_in'):
        abort(403)
    
    try:
        conn = get_db_connection()
        submissions = conn.execute('SELECT parola, frase_indizio, nome, timestamp FROM submissions ORDER BY timestamp DESC').fetchall()
        conn.close()
        
        output = []
        output.append(['Parola', 'Frase Indizio', 'Nome', 'Data'])
        for submission in submissions:
            output.append([
                submission['parola'],
                submission['frase_indizio'],
                submission['nome'] or 'Anonimo',
                submission['timestamp']
            ])
        
        # Create CSV response
        person_name = get_celebrated_person_name().lower().replace(' ', '_')
        response = make_response()
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=cruciverba_{person_name}.csv'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        # Write CSV data
        import io
        output_stream = io.StringIO()
        writer = csv.writer(output_stream)
        writer.writerows(output)
        response.data = output_stream.getvalue().encode('utf-8')
        
        logger.info(f"CSV export by admin from {get_remote_address()}")
        return response
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        flash("Errore durante l'esportazione", 'error')
        return redirect(url_for('admin'))

@app.route('/admin/delete/<int:submission_id>', methods=['POST'])
@limiter.limit("30 per minute")
def delete_submission(submission_id):
    if not session.get('admin_logged_in'):
        abort(403)
    
    try:
        # Validate submission_id
        if submission_id <= 0:
            abort(400)
            
        conn = get_db_connection()
        # Check if submission exists first
        result = conn.execute('SELECT id FROM submissions WHERE id = ?', (submission_id,)).fetchone()
        if not result:
            flash("Contributo non trovato", 'error')
            conn.close()
            return redirect(url_for('admin'))
            
        conn.execute('DELETE FROM submissions WHERE id = ?', (submission_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Submission {submission_id} deleted by admin from {get_remote_address()}")
        flash("Contributo eliminato", 'success')
    except Exception as e:
        logger.error(f"Delete submission error: {e}")
        flash("Errore durante l'eliminazione", 'error')
        
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/logout')
def form_logout():
    session.pop('form_access', None)
    flash("Sei stato disconnesso", 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True) 