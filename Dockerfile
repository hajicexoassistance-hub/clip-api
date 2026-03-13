FROM python:3.10-slim

# Install system dependencies with retries
RUN apt-get update || (sleep 5 && apt-get update) && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- LAYER CACHING OPTIMIZATION ----
# Copy ONLY requirements.txt first, so pip install is cached
# unless requirements.txt changes.
# This prevents re-downloading 3GB+ of AI libraries on code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy application code (this layer changes on every code update)
COPY . .

# Create necessary directories
RUN mkdir -p /app/output /app/data

# Set environment variables
ENV PORTRAITGEN_DB_PATH=/app/data/job_history.db
ENV PORTRAITGEN_OUTPUT_DIR=/app/output
ENV PORTRAITGEN_BASE_URL=/files/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
