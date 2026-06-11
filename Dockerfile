FROM alpine:latest

# Install required packages
RUN apk add --no-cache \
    curl \
    jq \
    bash \
    less \
    vim \
    coreutils \
    python3 \
    py3-pip \
    lsb-release \
    kubectl \
    openjdk21 \
    envsubst

# Set the working directory
WORKDIR /home/folio-eureka

# Copy application files
COPY folio-dev ./folio-dev/
COPY folio-test ./folio-test/
COPY folio-stage ./folio-stage/
COPY folio-prod ./folio-prod/
COPY ./*.yaml .
COPY ./*.json .
COPY ./*.py .
COPY ./*.jar .
COPY requirements.txt .

# Create virtual environment and install requirements
RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install -r requirements.txt

# Add activation of the virtual environment to the shell initialization
RUN echo "source /home/folio-eureka/venv/bin/activate" >> /home/folio-eureka/.bashrc

# Set the PATH for later commands
ENV PATH="/home/folio-eureka/venv/bin:$PATH"
