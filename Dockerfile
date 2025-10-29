# Multi-stage Dockerfile for Histology Collagen Quantification
# Uses pixi for reproducible environment management

FROM ghcr.io/prefix-dev/pixi:latest AS base

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY requirements.txt ./
COPY env.yaml ./

# Install pixi environment (includes all dependencies)
RUN pixi install -v

# Copy source code
COPY python/ ./python/
COPY stain_color_map/ ./stain_color_map/
COPY notebook/ ./notebook/

# Set environment variables
ENV PIXI_PROJECT_ROOT=/app
ENV PATH=/app/.pixi/envs/default/bin:$PATH

# Create directories for data
RUN mkdir -p /data/input /data/output

# Expose Jupyter port
EXPOSE 8888

# Default command: interactive shell
CMD ["pixi", "shell"]

# Alternative entrypoints (can be overridden):
# For Jupyter Lab: docker run -p 8888:8888 image pixi run notebook
# For deconvolution: docker run -v /path/to/data:/data image pixi run decon
# For segmentation: docker run -v /path/to/data:/data image pixi run seg
