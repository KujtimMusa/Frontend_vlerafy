FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for greenlet (SQLAlchemy dependency)
RUN apt-get update && apt-get install -y \
    g++ \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8000

# Use wrapper script instead of direct python command
ENTRYPOINT ["./start.sh"]
