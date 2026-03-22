FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/ .

EXPOSE 19100

CMD ["python", "-m", "waitress", "--host", "0.0.0.0", "--port", "19100", "server_v2:app"]
