FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ app/

ENV PORT=8000

# --no-access-log: el checador manda su token en ?token= y el access log lo escribiría.
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log
