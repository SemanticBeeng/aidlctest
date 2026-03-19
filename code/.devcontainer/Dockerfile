# Go Reverse Engineering Dev Container
FROM golang:1.23

# Install additional tools
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    gdb \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install additional tools for reverse engineering and Go development
RUN apt-get update && apt-get install -y \
    radare2 \
    binutils \
    strace \
    ltrace \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Install Go-specific tools
RUN go install github.com/go-delve/delve/cmd/dlv@latest \
    && go install github.com/securego/gosec/v2/cmd/gosec@latest \
    && go install honnef.co/go/tools/cmd/staticcheck@latest \
    && go install github.com/golangci-lint/golangci-lint/cmd/golangci-lint@latest

# Set up Go environment
ENV GOPATH=/go
ENV PATH=$GOPATH/bin:/usr/local/go/bin:$PATH

# Create a non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(ALL\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace
