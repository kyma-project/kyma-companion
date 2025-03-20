# Use Ubuntu Noble as the base image
FROM ubuntu:noble

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
  POETRY_VERSION=2.1.0 \
  POETRY_HOME="/opt/poetry" \
  POETRY_VENV="/opt/poetry-venv" \
  POETRY_CACHE_DIR="/opt/.cache"

# Install system dependencies
RUN apt-get update && apt dist-upgrade -y && apt-get install -y --no-install-recommends \
  python3 \
  python3-pip \
  python3-venv \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry 2.1
RUN python3 -m venv $POETRY_VENV \
  && $POETRY_VENV/bin/pip install -U pip setuptools wheel \
  && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

# Add Poetry to PATH
ENV PATH="${PATH}:${POETRY_VENV}/bin"

# Set the working directory
WORKDIR /app

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies using Poetry
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --without dev,test

# Copy the rest of the application code
COPY . .

# Expose the default FastAPI port
EXPOSE 8000

# Command to run the FastAPI application with Uvicorn
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
