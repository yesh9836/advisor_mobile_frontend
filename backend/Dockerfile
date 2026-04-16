FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY backend/requirements.lock /app/requirements.lock
RUN pip install --upgrade pip==24.2 && pip install -r /app/requirements.lock

COPY backend/ /app/
COPY shared/ /shared/

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
