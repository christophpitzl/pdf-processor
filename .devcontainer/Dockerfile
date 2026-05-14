FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Install common development tools and Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    bash \
 && rm -rf /var/lib/apt/lists/*

# The base image already has a 'vscode' user; ensure it has sudo access
RUN apt-get update && apt-get install -y sudo \
 && echo "vscode ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vscode \
 && chmod 0440 /etc/sudoers.d/vscode

USER vscode

WORKDIR /workspace
