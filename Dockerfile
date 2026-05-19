FROM python:3.11-alpine

# Install system dependencies (nfs-utils for NFS mount support)
RUN apk add --no-cache \
    poppler-utils \
    tesseract-ocr \
    curl \
    nfs-utils \
    shadow \
    && rm -rf /var/cache/apk/*

# Create entrypoint script for NFS mounting
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'set -e' >> /entrypoint.sh && \
    echo '' >> /entrypoint.sh && \
    echo '# Mount NFS if configured' >> /entrypoint.sh && \
    echo 'if [ -n "$NFS_SERVER" ] && [ -n "$NFS_EXPORT_PATH" ]; then' >> /entrypoint.sh && \
    echo '  echo "Mounting NFS share..."' >> /entrypoint.sh && \
    echo '  mkdir -p /mnt/nfs' >> /entrypoint.sh && \
    echo '  mount -t nfs -o "${NFS_MOUNT_OPTIONS:-hard,intr,noatime}" "${NFS_SERVER}:${NFS_EXPORT_PATH}" /mnt/nfs' >> /entrypoint.sh && \
    echo '  echo "NFS share mounted successfully"' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    echo '' >> /entrypoint.sh && \
    echo '# Execute the command' >> /entrypoint.sh && \
    echo 'exec "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

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

# Set entrypoint for NFS mounting
ENTRYPOINT ["/entrypoint.sh"]

# Run the application
# Use --web flag to start with web interface
CMD ["python", "-m", "src.main", "--web"]
