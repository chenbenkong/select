FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY . .
EXPOSE 7860
CMD ["python", "-u", "server.py"]
