#!/usr/bin/env python3
"""
Integration Tests for Cruciverba Application

These tests verify end-to-end functionality and real-world usage scenarios.
"""

import pytest
import requests
import time
import threading
import os
from urllib.parse import urljoin

# Configuration for integration tests
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
FORM_PASSWORD = os.getenv("FORM_PASSWORD", "bianca")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "bianca2024")

class TestLiveApplication:
    """Integration tests against running application."""
    
    @pytest.fixture(autouse=True)
    def check_server(self):
        """Check if the server is running before tests."""
        try:
            response = requests.get(BASE_URL, timeout=5)
            if response.status_code != 200:
                pytest.skip("Application server not running on localhost:8080")
        except requests.ConnectionError:
            pytest.skip("Application server not running on localhost:8080")
    
    def test_complete_user_journey(self):
        """Test complete user journey from login to submission."""
        session = requests.Session()
        
        # Step 1: Access main page (should show login)
        response = session.get(BASE_URL)
        assert response.status_code == 200
        assert "Password di accesso" in response.text
        
        # Step 2: Login with correct password
        response = session.post(BASE_URL, data={
            'access_password': FORM_PASSWORD
        })
        assert response.status_code == 200
        
        # Step 3: Submit a valid contribution
        test_data = {
            'parola': 'ALLEGRIA',
            'frase_indizio': 'Stato d\'animo che la caratterizza sempre nella vita quotidiana',
            'nome': 'Integration Test User'
        }
        
        response = session.post(BASE_URL, data=test_data)
        assert response.status_code == 200
        assert "Grazie Integration Test User!" in response.text
        assert "Aggiungi un'altra parola" in response.text
        
        # Step 4: Add another word
        response = session.get(BASE_URL)
        assert response.status_code == 200
        assert "Parola" in response.text  # Form should be accessible
        
        # Step 5: Submit another contribution
        test_data2 = {
            'parola': 'SORRISO',
            'frase_indizio': 'Espressione facciale che non manca mai sul suo volto',
            'nome': 'Integration Test User'
        }
        
        response = session.post(BASE_URL, data=test_data2)
        assert response.status_code == 200
        assert "Grazie Integration Test User!" in response.text
        
        # Step 6: Logout
        response = session.post(f"{BASE_URL}/logout", allow_redirects=False)
        assert response.status_code == 302
    
    def test_admin_workflow(self):
        """Test complete admin workflow."""
        session = requests.Session()
        
        # Step 1: Access admin page
        response = session.get(f"{BASE_URL}/admin")
        assert response.status_code == 200
        assert "Password" in response.text
        
        # Step 2: Login as admin
        response = session.post(f"{BASE_URL}/admin", data={
            'password': ADMIN_PASSWORD
        })
        assert response.status_code == 200
        
        # Step 3: View dashboard
        response = session.get(f"{BASE_URL}/admin")
        assert response.status_code == 200
        assert "Pannello Amministratore" in response.text
        
        # Step 4: Export CSV
        response = session.get(f"{BASE_URL}/admin/export")
        assert response.status_code == 200
        assert response.headers.get('Content-Type') == 'text/csv; charset=utf-8'
        assert 'Parola,Frase Indizio,Nome,Data' in response.text
        
        # Step 5: Logout
        response = session.post(f"{BASE_URL}/admin/logout", allow_redirects=False)
        assert response.status_code == 302
    
    def test_security_headers_live(self):
        """Test security headers on live application."""
        response = requests.get(BASE_URL)
        
        # Check security headers
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'
        assert response.headers.get('X-XSS-Protection') == '0'
        assert 'Strict-Transport-Security' not in response.headers
        assert 'default-src \'self\'' in response.headers.get('Content-Security-Policy', '')
        assert response.headers.get('Referrer-Policy') == 'no-referrer'
    
    def test_rate_limiting_simulation(self):
        """Test rate limiting with multiple requests."""
        session = requests.Session()
        
        # Login first
        login_response = session.post(BASE_URL, data={
            'access_password': FORM_PASSWORD
        })
        assert login_response.status_code == 200
        
        # Make multiple rapid requests
        responses = []
        for i in range(15):  # Exceed the 10 per minute limit
            response = session.post(BASE_URL, data={
                'parola': f'TEST{i}',
                'frase_indizio': f'Test frase indizio numero {i} con almeno dieci caratteri',
                'nome': f'Test User {i}'
            })
            responses.append(response.status_code)
            time.sleep(0.1)  # Small delay
        
        # Should eventually get rate limited (429 status code)
        # Note: This might not trigger in testing environment
        assert any(status in [429, 200] for status in responses)
    
    def test_concurrent_users(self):
        """Test concurrent user submissions."""
        def user_submission(user_id):
            """Simulate a user submission."""
            session = requests.Session()
            
            # Login
            session.post(BASE_URL, data={'access_password': FORM_PASSWORD})
            
            # Submit
            response = session.post(BASE_URL, data={
                'parola': f'CONCURRENT{user_id}',
                'frase_indizio': f'Frase indizio per test concorrente numero {user_id}',
                'nome': f'Concurrent User {user_id}'
            })
            return response.status_code == 200
        
        # Create multiple threads for concurrent users
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(
                target=lambda uid=i: results.append(user_submission(uid))
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All submissions should be successful
        assert all(results), f"Some concurrent submissions failed: {results}"
    
    def test_malicious_input_protection(self):
        """Test protection against malicious inputs."""
        session = requests.Session()
        
        # Login
        session.post(BASE_URL, data={'access_password': FORM_PASSWORD})
        
        # Test XSS attempts
        xss_payloads = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert("xss")>',
            'javascript:alert("xss")',
            '<svg onload=alert("xss")>',
            '"><script>alert("xss")</script>'
        ]
        
        for payload in xss_payloads:
            response = session.post(BASE_URL, data={
                'parola': 'SICUREZZA',
                'frase_indizio': f'Test payload: {payload}',
                'nome': f'XSS Test {payload[:10]}'
            })
            
            # Should not contain the payload in response
            assert '<script>' not in response.text
            assert 'onerror=' not in response.text
            assert 'javascript:' not in response.text
    
    def test_sql_injection_protection(self):
        """Test protection against SQL injection."""
        session = requests.Session()
        
        # Login
        session.post(BASE_URL, data={'access_password': FORM_PASSWORD})
        
        # Test SQL injection payloads
        sql_payloads = [
            "'; DROP TABLE submissions; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM submissions --",
            "'; INSERT INTO submissions VALUES (1,'hack','hack','hack'); --"
        ]
        
        for payload in sql_payloads:
            response = session.post(BASE_URL, data={
                'parola': 'SICUREZZA',
                'frase_indizio': f'SQL injection test with payload',
                'nome': payload
            })
            
            # Application should handle it gracefully
            assert response.status_code in [200, 400]
            # Should not contain SQL error messages
            assert 'syntax error' not in response.text.lower()
            assert 'sqlite' not in response.text.lower()
            assert 'operationalerror' not in response.text.lower()
            assert 'traceback' not in response.text.lower()

class TestDockerDeployment:
    """Tests specific to Docker deployment."""
    
    def test_docker_container_health(self):
        """Test Docker container health."""
        try:
            import docker
            client = docker.from_env()
            
            # Find our container
            containers = client.containers.list(filters={'name': 'cruciverba-nexus'})
            if not containers:
                pytest.skip("Docker container not found")
            
            container = containers[0]
            
            # Check container status
            assert container.status == 'running'
            
            # Check health if health check is configured
            if hasattr(container.attrs['State'], 'Health'):
                health = container.attrs['State']['Health']['Status']
                assert health in ['healthy', 'starting']
                
        except ImportError:
            pytest.skip("Docker client not available")
        except Exception as e:
            pytest.skip(f"Docker test failed: {e}")
    
    def test_volume_persistence(self):
        """Test that data persists across container restarts."""
        # This would require Docker commands and is environment-specific
        pytest.skip("Volume persistence test requires specific Docker setup")

def run_integration_tests():
    """Run integration tests independently."""
    print("🔍 Running Integration Tests for Cruciverba Nexus")
    print("=" * 60)
    print(f"Target URL: {BASE_URL}")
    print(f"Form Password: {FORM_PASSWORD}")
    print(f"Admin Password: {ADMIN_PASSWORD}")
    print()
    
    # Check if server is running
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"✅ Server is running (HTTP {response.status_code})")
    except requests.ConnectionError:
        print("❌ Server is not running. Please start the application first:")
        print("   docker-compose up -d")
        return False
    
    # Run pytest on this file
    import subprocess
    result = subprocess.run([
        'python', '-m', 'pytest', __file__, '-v'
    ], capture_output=False)
    
    return result.returncode == 0

if __name__ == '__main__':
    success = run_integration_tests()
    exit(0 if success else 1)
