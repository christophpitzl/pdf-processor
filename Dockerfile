FROM --platform=$BUILDPLATFORM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

# Run the application
# Use --web flag to start with web interface
CMD ["python", "-m", "src.main", "--web"]
