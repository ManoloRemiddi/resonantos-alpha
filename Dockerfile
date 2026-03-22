FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/ .

ENV SKIP_VALIDATION=1
EXPOSE 19100

CMD ["python", "-m", "waitress", "--host", "0.0.0.0", "--port", "19100", "--threads", "8", "server_v2:app"]
