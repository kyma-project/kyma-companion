FROM python:3.12-slim-bookworm as builder

# Set the working directory in the container
WORKDIR /app

# Copy only necessary files
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY data ./data
COPY config ./config

# Install Poetry and dependencies in one layer
RUN pip install --no-cache-dir poetry>=2.0  \
  && poetry config virtualenvs.create false \
  && poetry install --without test,dev --no-interaction --no-ansi \
  && pip uninstall -y poetry

# Start a new stage for a smaller final image
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Run the command to start Uvicorn
CMD ["fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
