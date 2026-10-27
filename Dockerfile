# Lab base; resolve and review its digest before a production release.
FROM python:3.12-slim
WORKDIR /app
COPY --chown=10001:10001 app.py ./app.py
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8080
EXPOSE 8080
CMD ["python", "app.py"]
