#!/usr/bin/env python3
"""
Test Runner for Cruciverba Application

This script runs the complete test suite and generates a coverage report.
Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --fast       # Run only fast tests
    python run_tests.py --security   # Run only security tests
    python run_tests.py --coverage   # Run with coverage report
"""

import sys
import subprocess
import argparse
import os

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🔍 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        print("Please install the required dependencies:")
        print("pip install -r requirements.txt")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run tests for Cruciverba application")
    parser.add_argument('--fast', action='store_true', 
                       help='Run only fast tests (exclude slow marker)')
    parser.add_argument('--security', action='store_true',
                       help='Run only security-related tests')
    parser.add_argument('--auth', action='store_true',
                       help='Run only authentication tests')
    parser.add_argument('--admin', action='store_true',
                       help='Run only admin functionality tests')
    parser.add_argument('--coverage', action='store_true',
                       help='Run tests with coverage report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--html', action='store_true',
                       help='Generate HTML coverage report')
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add verbosity
    if args.verbose:
        cmd.append('-vv')
    else:
        cmd.append('-v')
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend(['--cov=app', '--cov-report=term-missing'])
        if args.html:
            cmd.append('--cov-report=html')
    
    # Add specific test markers
    if args.fast:
        cmd.extend(['-m', 'not slow'])
    elif args.security:
        cmd.extend(['-m', 'security'])
    elif args.auth:
        cmd.extend(['-m', 'auth'])
    elif args.admin:
        cmd.extend(['-m', 'admin'])
    
    # Add test file
    cmd.append('test_app.py')
    
    print("🎓 Cruciverba Application Test Suite")
    print("=" * 50)
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("❌ app.py not found. Make sure you're in the correct directory.")
        return 1
    
    # Install dependencies if needed
    if args.coverage and not os.path.exists('requirements.txt'):
        print("⚠️  requirements.txt not found. Installing basic dependencies...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytest', 'pytest-flask', 'pytest-cov'], check=True)
    
    # Run the tests
    success = run_command(cmd, "Running test suite")
    
    if success:
        print("\n🎉 All tests completed successfully!")
        
        if args.coverage and args.html:
            print("\n📊 Coverage report generated in htmlcov/index.html")
            
        print("\n📋 Test Summary:")
        print("- Security: Headers, CSRF, XSS protection, rate limiting")
        print("- Authentication: Form login, admin login, logout")
        print("- Form submission: Validation, sanitization, duplicates")
        print("- Admin functionality: Dashboard, CSV export, delete")
        print("- Error handling: 404, invalid inputs, edge cases")
        print("- Database operations: CRUD, data integrity")
        print("- Success page: Add another word functionality")
        
        return 0
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 