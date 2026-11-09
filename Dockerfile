FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ابتدا وابستگی‌ها (برای کش بهتر لایه‌های داکر)
COPY requirements.txt .
RUN pip install -r requirements.txt

# سپس کد پروژه
COPY src ./src

# کاربر غیر root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Railway متغیر PORT را خودش ست می‌کند؛ پیش‌فرض 8501
ENV PORT=8501
EXPOSE 8501

CMD ["sh", "-c", "streamlit run src/app.py \
  --server.port=${PORT} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false"]
