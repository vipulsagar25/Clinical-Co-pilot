# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (needed for compiling some python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file (Assumes req.txt is in the parent directory of server_rag)
# Note: For Docker context, we usually copy the req.txt directly to /app/
# Wait, let's copy req.txt properly. The user has req.txt at root `Clinical Co-pilot/req.txt`
COPY ../req.txt /app/req.txt

# Install python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r req.txt

# Copy project files
COPY . /app/server_rag/

# The uvicorn server will run on port 10000 by default (Render standard)
EXPOSE 10000

# Set Python Path so 'app' and 'api' can be resolved
ENV PYTHONPATH=/app/server_rag

# Start FastAPI server via Uvicorn
CMD ["uvicorn", "server_rag.api.main:app", "--host", "0.0.0.0", "--port", "10000"]
