FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 (lxml 빌드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000

# 컨테이너가 정상인지 30초마다 확인한다 (/health 엔드포인트 체크)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
