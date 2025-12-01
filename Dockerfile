# Multi-stage build: Test stage first, then production
FROM python:3.11-slim AS test-stage

WORKDIR /app

# Install system dependencies for testing
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install all dependencies (including test deps)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create test user
RUN adduser --disabled-password --gecos '' testuser && \
    chown -R testuser:testuser /app && \
    mkdir -p /app/data && \
    chown testuser:testuser /app/data

USER testuser

# Set test environment
ENV FLASK_ENV=testing
ENV DEBUG=False
ENV SECRET_KEY=build-test-secret-key
ENV FORM_PASSWORD=bianca
ENV ADMIN_PASSWORD=bianca2024
ENV CELEBRATED_PERSON_NAME=Bianca

# Run tests - BUILD WILL FAIL IF TESTS FAIL
RUN python -m pytest test_app.py -v --tb=short

# Production stage - only built if tests pass
FROM python:3.11-slim AS production

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy production requirements and install only production dependencies
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application files (excluding test files)
COPY --from=test-stage /app/app.py .
COPY --from=test-stage /app/templates/ ./templates/
# Copy static files only if they exist
RUN mkdir -p ./static

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/data && \
    chown appuser:appuser /app/data

USER appuser

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run the application
CMD ["python", "app.py"] 