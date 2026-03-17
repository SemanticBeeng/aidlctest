# Dev container for running Qwen3-0.6B QAT evaluations on RunPod
# Base: PyTorch with CUDA — matches RunPod's native GPU images
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Avoid interactive prompts during package installs
ENV DEBIAN_FRONTEND=noninteractive

# System packages needed for dev workflow
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    openssh-server \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install uv — fast Python package manager (single static binary)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV PATH="/usr/local/bin:${PATH}"

# Create non-root user for VS Code (RunPod defaults to root)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/$USERNAME

# Build cache directory — named volume, holds venv, pkg-cache, __pycache__, etc.
RUN mkdir -p /buildcache && chown $USER_UID:$USER_GID /buildcache

# SSH config for VS Code Remote
RUN mkdir -p /run/sshd \
    && sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

WORKDIR /workspace
