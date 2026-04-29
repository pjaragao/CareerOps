FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

# Install system dependencies (only the ones not in the image if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc fluxbox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/output /app/auth

EXPOSE 8000

ENV DISPLAY=:99
ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
