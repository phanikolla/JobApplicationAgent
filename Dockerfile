FROM python:3.11-slim

# Install system dependencies required by Playwright/Chromium
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libexpat1 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    wget \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright + Chromium browser
RUN playwright install chromium

# Copy the modular application source
COPY src/ src/
COPY config.json ./

# Copy the master resume and applicant profile
COPY Phani_Kumar_Kolla_profile.pdf .
COPY applicant_profile.md .

# Copy static frontend files
COPY static/ static/

# Create output directory
RUN mkdir -p output

# Expose web dashboard port (8080 required by Google Cloud Run)
EXPOSE 8080

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8080"]
