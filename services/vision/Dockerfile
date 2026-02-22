FROM python:3.11-slim

WORKDIR /app

# Install dependencies (Caching layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .
RUN pip install --no-cache-dir -e .

# Expose FastAPI default port
EXPOSE 8000

# Run Uvicorn server dynamically connecting to host configurations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
