# Use a specific Python base image based on your requirements
FROM python:3.11-slim-buster

# Set a working directory
WORKDIR /app

# RUN apk add python3-dev build-base linux-headers pcre-dev

# # Update package lists
# RUN apk update

# # Install dependencies
# RUN apk add --no-cache uwsgi python3-dev py-pip

# Add trusted host and extra index url to pip.conf
RUN mkdir -p /root/.config/pip && echo "[global]\nextra-index-url = https://int.repositories.cloud.sap/artifactory/api/pypi/proxy-deploy-releases-hyperspace-pypi/simple\ntrusted-host = int.repositories.cloud.sap" > /root/.config/pip/pip.conf
# RUN echo "[global]\nextra-index-url = https://int.repositories.cloud.sap/artifactory/api/pypi/proxy-deploy-releases-hyperspace-pypi/simple\ntrusted-host = int.repositories.cloud.sap" > /etc/pip.conf

# ENV PIP_CONFIG_FILE /etc/pip.conf

# RUN echo $(pip config list)

# Copy requirements.txt and install dependencies
COPY requirements.txt ./
RUN pip install unstructured --no-deps urllib3
RUN pip install -r requirements.txt
RUN pip install --no-cache-dir "sap-llm-commons[all]"==0.2.0
RUN pip install gunicorn

RUN apt-get update
RUN apt-get install -y curl

RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
RUN chmod +x ./kubectl
RUN mv ./kubectl /usr/local/bin

# Copy your application code
COPY . .

# Expose Flask's default port (5000)
EXPOSE 5000

# Set the Flask app command using environment variable (optional)
# This prevents hardcoding Flask's location within the container
ENV FLASK_APP=main.py

# Start the Flask app using uWSGI (recommended for production)
# CMD ["uwsgi", "--ini", "uwsgi.ini"]

# Alternative startup command for development (optional)
# Use this only for development, not production, due to security concerns
# CMD ["flask", "run", "--host", "0.0.0.0", "--debug"]
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--timeout", "180", "main:app", "-w", "1", "--limit-request-line", "4096", "--limit-request-fields", "100", "--limit-request-field_size", "0", "--worker-class", "gevent"]