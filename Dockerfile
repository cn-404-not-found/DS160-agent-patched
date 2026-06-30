FROM python:3.10-slim-bookworm

LABEL org.opencontainers.image.title="DS-160 Visa Assistant"
LABEL org.opencontainers.image.description="One-click DS-160 form filler for China B1/B2 applicants"

# Chromium and headless dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-common \
    fonts-noto-cjk \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libnss3 \
    libpango-1.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Chromium path for Playwright-compatible discovery
ENV CHROMIUM_PATH=/usr/bin/chromium
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Create non-root user for Chrome
RUN useradd --create-home --shell /bin/bash ds160 && \
    mkdir -p /home/ds160/chrome-profile && \
    chown -R ds160:ds160 /home/ds160

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY app/ app/
COPY sample_data/ sample_data/
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose ports: 8765 (API/UI), 9222 (CDP)
EXPOSE 8765 9222

ENV PYTHONPATH=/app/src
ENV CDP_PORT=9222
ENV DOSSIER_PATH=/app/sample_data/china_b1b2_sample.json

USER ds160
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
