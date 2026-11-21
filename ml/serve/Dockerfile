# Neutral Ground ml-serve (FastAPI). Build context: the repo root.
# Trained artifacts are not baked in: mount ml/artifacts at /app/ml/artifacts.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 app
WORKDIR /app
COPY ml/requirements.txt ml/requirements.txt
COPY ml/serve/requirements.txt ml/serve/requirements.txt
RUN pip install --no-cache-dir -r ml/requirements.txt -r ml/serve/requirements.txt
COPY ml ml
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "ml.serve.app:app", "--host", "0.0.0.0", "--port", "8000"]
