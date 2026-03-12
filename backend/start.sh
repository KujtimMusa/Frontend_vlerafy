#!/bin/sh
# Get port from Railway environment or default to 8000
PORT=${PORT:-8000}

# Start Uvicorn directly
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT


