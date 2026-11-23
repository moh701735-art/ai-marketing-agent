# رادار المنافسين: خدمة داخلية صغيرة (لا منافذ منشورة). السياق = /opt/central/competitor_radar
FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home radar && pip install --no-cache-dir "psycopg[binary]==3.2.3"
WORKDIR /app
COPY service /app/competitor_radar/service
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8088
CMD ["python", "-m", "competitor_radar.service.app"]
