FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_DATA_DIR=/app/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip && \
    python -m pip install .

COPY server.py register_all.py oauth_service.py mail_service.py sub2api_uploader.py config.example.json ./
COPY web ./web
COPY docker/entrypoint.sh /usr/local/bin/gpt-account-register-entrypoint

RUN sed -i 's/\r$//' /usr/local/bin/gpt-account-register-entrypoint && \
    chmod +x /usr/local/bin/gpt-account-register-entrypoint && \
    mkdir -p /app/data

EXPOSE 18421
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18421/api/status', timeout=3)"

ENTRYPOINT ["gpt-account-register-entrypoint"]
CMD ["python", "server.py"]
