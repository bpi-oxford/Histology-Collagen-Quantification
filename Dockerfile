# Multi-stage Dockerfile for Histology Collagen Quantification
# Uses pixi for reproducible environment management
# Force Linux x86_64 platform for consistent builds

FROM --platform=linux/amd64 ghcr.io/prefix-dev/pixi:latest AS base

WORKDIR /app

# Copy project configuration files
COPY env.yaml ./
COPY requirements.txt ./

# Install system dependencies including Java (required for python-javabridge/histomicstk)
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for python-javabridge
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Create temporary env.yaml without pip requirements for pixi import
RUN grep -v '\-r requirements.txt' env.yaml > env_pixi.yaml

# Initialize pixi from conda env.yaml and install dependencies (includes pytest)
RUN pixi init --import env_pixi.yaml && pixi install -v

# Install histomicstk FIRST (with BuildKit cache mount for faster rebuilds)
# This prevents pyHisto from trying to build it from source
RUN --mount=type=cache,target=/root/.cache/pip \
    pixi run python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels

# Install Python dependencies from requirements.txt (excluding pyHisto and comments)
# Create temporary requirements file without pyHisto
RUN --mount=type=cache,target=/root/.cache/pip \
    grep -v '^#' requirements.txt | grep -v '^$' | grep -v 'pyHisto' > /tmp/requirements_temp.txt && \
    pixi run pip install -r /tmp/requirements_temp.txt && \
    rm /tmp/requirements_temp.txt

# Copy pyHisto dependency first (from git submodule)
COPY dependency/pyHisto/ ./dependency/pyHisto/

# Install pyHisto in editable mode with --no-deps (since histomicstk is already installed)
RUN pixi run pip install --no-deps -e ./dependency/pyHisto

# Clean up temporary file
RUN rm env_pixi.yaml

# Copy source code
COPY python/ ./python/
COPY stain_color_map/ ./stain_color_map/
COPY notebook/ ./notebook/

# Set environment variables
ENV PIXI_PROJECT_ROOT=/app
ENV PATH=/app/.pixi/envs/default/bin:$PATH

# Create directories for data
RUN mkdir -p /data

# Expose Jupyter port
EXPOSE 8888

# Default command: interactive bash shell with pixi environment activated
CMD ["pixi", "shell"]
