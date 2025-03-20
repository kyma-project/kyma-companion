FROM python:3.12-slim-bullseye AS builder

# Set the working directory in the container
WORKDIR /app

# Copy only necessary files
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY data ./data
COPY config ./config

# Install Poetry and dependencies in one layer
RUN apt update && apt dist-upgrade -y && apt install -y build-essential gcc clang 
RUN pip install --no-cache-dir poetry>=2.1  \
  && poetry config virtualenvs.create false \
  && poetry install --without dev,test --no-interaction --no-ansi \
  && pip uninstall -y poetry

# Start a new stage for a smaller final image
FROM python:3.12-alpine

WORKDIR /app

# Copy Python environment and app files from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

# Install necessary runtime dependencies
RUN apk update && apk upgrade && \
  apk add --no-cache libstdc++

# Create a non-root user
RUN adduser -u 5678 -D appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Run the command to start Uvicorn
CMD ["fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
