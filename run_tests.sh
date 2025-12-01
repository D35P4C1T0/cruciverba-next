#!/bin/bash

# Cruciverba Test Runner Script
# Usage: ./run_tests.sh [unit|integration|all|coverage]

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}🎓 Cruciverba Test Suite${NC}"
    echo "=================================="
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Cleanup function
cleanup() {
    print_info "Cleaning up test containers..."
    docker-compose -f docker-compose.test.yml down --remove-orphans 2>/dev/null || true
    docker-compose down 2>/dev/null || true
}

# Trap cleanup on script exit
trap cleanup EXIT

run_unit_tests() {
    print_info "Building test environment..."
    docker-compose -f docker-compose.test.yml build test-runner
    
    print_info "Running unit tests..."
    if docker-compose -f docker-compose.test.yml run --rm test-runner; then
        print_success "Unit tests passed!"
        return 0
    else
        print_error "Unit tests failed!"
        return 1
    fi
}

run_integration_tests() {
    print_info "Starting application for integration tests..."
    docker-compose up -d
    
    # Wait for app to be ready
    print_info "Waiting for application to be ready..."
    sleep 10
    
    # Check if app is responding
    if curl -f http://localhost:8080 >/dev/null 2>&1; then
        print_success "Application is ready"
    else
        print_error "Application failed to start"
        docker-compose logs cruciverba-app
        return 1
    fi
    
    print_info "Building integration test environment..."
    docker-compose -f docker-compose.test.yml build integration-test
    
    print_info "Running integration tests..."
    if docker-compose -f docker-compose.test.yml --profile integration run --rm integration-test; then
        print_success "Integration tests passed!"
        return 0
    else
        print_error "Integration tests failed!"
        return 1
    fi
}

run_coverage_tests() {
    print_info "Running tests with coverage..."
    docker-compose -f docker-compose.test.yml build test-runner
    
    if docker-compose -f docker-compose.test.yml run --rm test-runner \
        python -m pytest test_app.py -v --cov=app --cov-report=term-missing --cov-report=html; then
        print_success "Coverage tests completed!"
        print_info "Coverage report generated in htmlcov/ directory"
        return 0
    else
        print_error "Coverage tests failed!"
        return 1
    fi
}

# Main execution
print_status

case "${1:-all}" in
    "unit")
        run_unit_tests
        ;;
    "integration") 
        run_integration_tests
        ;;
    "coverage")
        run_coverage_tests
        ;;
    "all")
        print_info "Running complete test suite..."
        echo
        
        # Run unit tests
        if run_unit_tests; then
            echo
            # Run integration tests  
            if run_integration_tests; then
                echo
                print_success "🎉 All tests passed successfully!"
                echo
                print_info "Test Summary:"
                echo "- ✅ Unit Tests: Security, Authentication, Forms, Admin"
                echo "- ✅ Integration Tests: End-to-end user journeys"
                echo "- ✅ Security Tests: XSS, CSRF, Rate Limiting, Headers"
                echo "- ✅ Database Tests: CRUD operations, data integrity"
                exit 0
            else
                print_error "Integration tests failed"
                exit 1
            fi
        else
            print_error "Unit tests failed"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 [unit|integration|all|coverage]"
        echo
        echo "Commands:"
        echo "  unit         - Run unit tests only"
        echo "  integration  - Run integration tests only"  
        echo "  coverage     - Run tests with coverage report"
        echo "  all          - Run all tests (default)"
        echo
        echo "Examples:"
        echo "  $0 unit      # Fast unit tests"
        echo "  $0 coverage  # Generate coverage report"
        echo "  $0           # Run everything"
        exit 1
        ;;
esac 