FROM python:3.12-slim-bookworm

# Screen and remote view (Xvfb, a small window manager, x11vnc + noVNC)
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb fluxbox x11vnc novnc websockify curl xz-utils openssl ca-certificates fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*
# Node for the browser tools of the Claude routine: they need 20+, and Debian's is 18
RUN curl -fsSL https://nodejs.org/dist/v22.22.1/node-v22.22.1-linux-x64.tar.xz | tar -xJ -C /usr/local --strip-components=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && npm install -g @playwright/mcp@0.0.83 \
    && ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html

COPY worker ./worker
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
# The same extension you use, from an extra build context (docker-compose.yml)
COPY --from=extension . /app/extension

ENV PYTHONUNBUFFERED=1
CMD ["/entrypoint.sh"]
