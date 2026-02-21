FROM python:3.11-slim

WORKDIR /app

# Install dependencies (Caching layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose Weaver port (8001 to prevent conflict with Vision)
EXPOSE 8001

# Run Uvicorn server dynamically connecting to host configurations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
