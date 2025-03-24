FROM ghcr.io/gardenlinux/gardenlinux:1592.6 AS builder
WORKDIR /app

# Copy only necessary files
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY data ./data
COPY config ./config

# Install Poetry and dependencies in one layer
RUN apt update &&  apt dist-upgrade&& apt install -y build-essential gcc python3.12 python3.12-venv python3.12-dev adduser \
  && python3.12 -m venv ./venv \
  && ./venv/bin/pip install --no-cache-dir poetry>=2.1 \
  && ./venv/bin/poetry config virtualenvs.create false \
  && ./venv/bin/poetry install --without dev,test --no-interaction --no-ansi \
  && ./venv/bin/pip uninstall -y poetry

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
