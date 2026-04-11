FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything
COPY . .

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Command
CMD ["uvicorn", "main:asgi_app", "--host", "0.0.0.0", "--port", "8080"]
