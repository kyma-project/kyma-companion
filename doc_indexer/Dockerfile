FROM ghcr.io/gardenlinux/gardenlinux:1592.12 AS builder
WORKDIR /app

# Copy only necessary files
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY docs_sources.json ./

# Install Poetry and dependencies in one layer
RUN apt update &&  apt dist-upgrade -y && apt install -y build-essential gcc python3.13 python3.13-venv adduser git \
  && python3.13 -m venv ./.venv \
  && ./.venv/bin/pip install --no-cache-dir poetry>=2.1 \
  && ./.venv/bin/poetry config virtualenvs.create false \
  && ./.venv/bin/poetry install --only main --no-interaction --no-ansi \
  && ./.venv/bin/pip uninstall -y poetry

# Clean up
RUN apt remove build-essential gcc -y && apt clean -y && apt autoremove -y && apt autoclean -y && rm -rf /var/lib/apt/lists/* 

# Create the non-root user and application directories
RUN useradd -u 10001 --create-home --shell /bin/bash appuser \
    && mkdir -p data \
    && chown -R appuser /app

ENV PATH="/app/.venv/bin:$PATH"

# Switch to the non-root user
USER appuser