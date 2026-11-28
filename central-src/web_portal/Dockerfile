# بوابة الزبائن: خدمة داخلية صغيرة (لا منافذ منشورة؛ Caddy يوصلها بالشبكة الداخلية). السياق = /opt/central/web_portal
FROM python:3.12-slim
RUN useradd --system --uid 10002 --no-create-home webportal && pip install --no-cache-dir "psycopg[binary]==3.2.3"
WORKDIR /app
COPY service /app/web_portal/service
RUN touch /app/web_portal/__init__.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10002
EXPOSE 8090
CMD ["python", "-m", "web_portal.service.app"]
