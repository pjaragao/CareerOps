FROM python:3.12-slim

WORKDIR /app

# curl: container healthcheck (docker-compose)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Extra build contexts from docker-compose: master CVs, LinkedIn texts and settings; the browser extension (served as a zip)
COPY --from=config . /app/config
COPY --from=extension . /app/extension
RUN mkdir -p /app/output /app/auth

EXPOSE 8000
ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
