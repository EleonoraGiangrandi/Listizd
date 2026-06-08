FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# Configura una cartella fissa e accessibile per i browser di Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

COPY . .

RUN chmod -R 777 /app

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]