FROM python:3.11-slim

WORKDIR /app

COPY lean/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lean/lean_api.py .

CMD ["python", "lean_api.py"]
