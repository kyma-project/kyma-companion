# Use a specific Python base image based on your requirements
FROM python:3.11-slim-buster

ARG JFROG_USER
ARG JFROG_TOKEN

# Create a group and user
RUN groupadd -r actionuser && useradd -r -g actionuser -d /home/actionuser actionuser


# Create the user's home directory and set appropriate permissions
RUN mkdir -p /home/actionuser/.config/pip && chown -R actionuser:actionuser /home/actionuser

# Set the home directory variable
ENV HOME=/home/actionuser

# Set a working directory
WORKDIR /app

# Copy your application code
COPY . .

# Change ownership of the working directory
RUN chown -R actionuser:actionuser /app

# Switch to the non-root user
USER actionuser

# Add .local/bin to the PATH environment variable
ENV PATH=/home/actionuser/.local/bin:$PATH

# Add trusted host and extra index url to pip.conf
RUN mkdir -p $HOME/.config/pip && echo "[global]\nextra-index-url = https://${JFROG_USER}:${JFROG_TOKEN}@common.repositories.cloud.sap/artifactory/api/pypi/deploy-releases-hyperspace-pypi/simple\ntrusted-host = common.repositories.cloud.sap" > $HOME/.config/pip/pip.conf
# RUN echo "[global]\nextra-index-url = https://int.repositories.cloud.sap/artifactory/api/pypi/proxy-deploy-releases-hyperspace-pypi/simple\ntrusted-host = int.repositories.cloud.sap" > /etc/pip.conf

# Change ownership of the application directory and the pip config directory to the non-root user
RUN chown -R actionuser:actionuser /app /home/actionuser/.config/pip

# Copy requirements.txt and install dependencies
# COPY requirements.txt ./
RUN pip install unstructured --no-deps urllib3
RUN pip install -r requirements.txt
RUN pip install --no-cache-dir "sap-llm-commons[all]"==0.2.0
RUN pip install gunicorn

#RUN apt-get update
#RUN apt-get install -y curl

RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
RUN chmod +x ./kubectl
RUN mv ./kubectl /usr/local/bin



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
