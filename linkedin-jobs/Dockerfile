FROM python:3.12-slim

# Install system dependencies for Playwright/Chromium + VNC
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libwayland-client0 \
    xvfb x11vnc fluxbox novnc websockify \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium
RUN pip install playwright && playwright install chromium

# Copy application code
COPY . .

RUN chmod +x /app/start.sh

# Create necessary directories
RUN mkdir -p /app/output /app/auth

EXPOSE 5050 6080

ENV DISPLAY=:99

CMD ["/app/start.sh"]
