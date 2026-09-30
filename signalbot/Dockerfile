FROM python:3.11-slim
WORKDIR /app
COPY signalbot/requirements.txt signalbot/requirements.txt
RUN pip install --no-cache-dir -r signalbot/requirements.txt
COPY signalbot signalbot
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "signalbot.app:app", "--host", "0.0.0.0", "--port", "8080"]
