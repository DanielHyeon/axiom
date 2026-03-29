FROM python:3.11-slim

WORKDIR /app

COPY shared/ /app/shared/
RUN pip install --no-cache-dir -e /app/shared

COPY vision/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vision/ .
RUN pip install --no-cache-dir -e .

# Expose FastAPI default port
EXPOSE 8000

# 컨테이너가 정상인지 30초마다 확인한다 (/health 엔드포인트 체크)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run Uvicorn server dynamically connecting to host configurations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
