FROM python:3.11-alpine

# Install system dependencies (no NFS utils needed — host folders are mapped via Docker volumes)
RUN apk add --no-cache \
    poppler-utils \
    tesseract-ocr \
    curl \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose web interface port
EXPOSE 8080

# Run the application
# Use --web flag to start with web interface
CMD ["python", "-m", "src.main", "--web"]
