#!/bin/bash

#!/bin/bash

# Build script with mandatory testing for Cruciverba Nexus
# Ensures no broken code can be deployed

set -e

MODE=${1:-"production"}

echo "🚀 Building Cruciverba Nexus application (Mode: $MODE)"
echo "🧪 All tests must pass for build to succeed"

case $MODE in
    "test-only")
        echo "🔍 Running tests only..."
        docker build --no-cache --target test-stage -t cruciverba-nexus-test .
        echo "✅ All tests passed!"
        ;;
    "development")
        echo "🛠️ Building development version..."
        docker build --no-cache --target test-stage -t cruciverba-nexus-test .
        docker build --no-cache -t cruciverba-nexus-app .
        echo "✅ Development build completed with all tests passed!"
        ;;
    "production")
        echo "🏭 Building production version..."
        docker build --no-cache --target test-stage -t cruciverba-nexus-test .
        docker build --no-cache -t cruciverba-nexus-app .
        echo "✅ Production build completed with all tests passed!"
        ;;
    "ci")
        echo "🤖 CI/CD Pipeline build..."
        docker build --no-cache --target test-stage -t cruciverba-nexus-test .
        docker build --no-cache -t cruciverba-nexus-app .
        echo "✅ CI build completed with all tests passed!"
        ;;
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage: $0 [test-only|development|production|ci]"
        exit 1
        ;;
esac

echo ""
echo "🎉 Build completed successfully!"
echo "💡 Note: This build cannot succeed unless all tests pass" 