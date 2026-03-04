FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md config.example.yaml config.yaml ./
COPY app ./app
COPY scripts ./scripts

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
