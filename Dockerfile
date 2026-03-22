FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/ .

EXPOSE 19100

CMD ["python", "server_v2.py"]
