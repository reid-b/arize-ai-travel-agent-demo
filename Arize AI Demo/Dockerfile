FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Non-root user; /app/data holds the saved fare history.
RUN useradd --create-home sojourns \
    && mkdir -p /app/data \
    && chown -R sojourns:sojourns /app \
    && chmod +x /app/docker/entrypoint.sh
USER sojourns

ENV SOJOURNS_PRICE_HISTORY=/app/data/price_history.json
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# The entrypoint waits for Phoenix (if PHOENIX_COLLECTOR_ENDPOINT is set), then runs the CMD.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
