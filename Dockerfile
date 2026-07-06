FROM python:3.11-slim
WORKDIR /app
COPY . .
EXPOSE 7860
CMD ["python", "server.py"]
