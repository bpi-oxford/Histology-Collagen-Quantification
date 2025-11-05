# Docker Usage Guide

Complete guide for using Docker with the Histology Collagen Quantification pipeline.

## Table of Contents

- [Building the Docker Image](#building-the-docker-image)
- [Running Interactive CLI](#running-interactive-cli)
- [Jupyter Notebook Integration](#jupyter-notebook-integration-with-vs-code)
- [Running Workflows Directly](#running-workflows-directly)
- [Apptainer/Singularity Conversion](#apptainersingularity-conversion-and-usage)
- [Docker Compose](#docker-compose-advanced)
- [Best Practices](#best-practices-for-docker-usage)

## Building the Docker Image
This repository includes a private dependency (`pyHisto` from Oxford-Zeiss-Centre-of-Excellence). You have two options:

#### Option 1: GitHub Personal Access Token (Recommended for sharing)

This allows external users to build the image without needing SSH keys.

**1. Create a GitHub Personal Access Token** (classic):
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with `repo` scope (full control of private repositories)
   - Copy the token (e.g., `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

**2. Build the Docker image** with the token:
```bash
# Pass the token as a build argument
docker build --build-arg GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx -t collagen-quant .

# Or use an environment variable (more secure, keeps token out of shell history)
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
docker build --build-arg GITHUB_TOKEN -t collagen-quant .
```

#### Option 2: SSH Key Authentication (For personal use)

If you have SSH access configured:

1. **Update requirements.txt** to use HTTPS instead of SSH:
   ```bash
   # Change line 16 in requirements.txt from:
   # git+ssh://git@github.com/Oxford-Zeiss-Centre-of-Excellence/pyHisto.git
   # to:
   # git+https://github.com/Oxford-Zeiss-Centre-of-Excellence/pyHisto.git
   ```

2. **Build normally** (will use your local git credentials if authenticated)

#### Security Best Practices

- ❌ Never commit tokens to version control
- ✅ Use GitHub secrets for CI/CD pipelines
- ✅ Revoke tokens after use if sharing with external users
- ✅ Consider creating a dedicated read-only token for Docker builds
- ✅ The Dockerfile automatically removes git credentials after pip install completes

**Note:** The Dockerfile is configured to build for `linux/amd64` (x86_64) by default, ensuring consistency across all platforms including Apple Silicon Macs.

## Running Interactive CLI

Run the container with an interactive shell to execute processing scripts:

```bash
# Basic interactive session
docker run -it --rm \
  -v /path/to/your/raw_images:/data
  collagen-quant

# Inside the container, activate pixi and run workflows
pixi shell

# run interactive deconvolution
bash python/decon.sh

# run interactive segmentation
bash python/seg.sh
```

- `-v /path/to/your/raw_images:/data` - Mount your data folder
- `--rm` - Automatically remove container when it exits
- `-it` - Interactive terminal

## Jupyter Notebook Integration with VS Code

Run Jupyter Lab inside the container and connect from VS Code on your host machine:

### Start Jupyter Lab

```bash
# Start container with Jupyter Lab
docker run -it --rm \
  -p 8888:8888 \
  -v /path/to/your/data:/data \
  -v $(pwd)/notebook:/app/notebook \
  collagen-quant \
  pixi run notebook
```

### Connect from VS Code

1. The terminal will display a URL like: `http://127.0.0.1:8888/lab?token=abc123...`
2. In VS Code:
   - Install the "Jupyter" extension if not already installed
   - Press `Cmd/Ctrl + Shift + P` → "Jupyter: Specify Jupyter Server for Connections"
   - Select "Existing" → Paste the URL with token
   - Open any `.ipynb` file and select the kernel from the remote server

### Alternative: Direct Browser Access

```bash
# Copy token from the Jupyter output, then:
# Open browser to http://localhost:8888 and paste the token
```

## Running Workflows Directly

Execute specific workflows without entering the container shell:

### Color Deconvolution

```bash
docker run -it --rm \
  -v /path/to/raw_images:/data/input \
  -v /path/to/output:/data/output \
  collagen-quant \
  pixi run decon
```

### Segmentation

```bash
docker run -it --rm \
  -v /path/to/processed_data:/data/input \
  -v /path/to/output:/data/output \
  collagen-quant \
  pixi run seg
```

## Apptainer/Singularity Conversion and Usage

For HPC environments that use Apptainer (formerly Singularity), you can convert the Docker image.

### Converting Docker Image to SIF

Build the Docker image locally, then export and convert to SIF on your HPC cluster:

**1. On your local machine with Docker**, build and export the image:

```bash
# Build the Docker image (see GitHub token setup above if using private repos)
docker build -t collagen-quant .

# Save the image to a tar file
docker save collagen-quant:latest -o collagen-quant.tar

# Compress for faster transfer
gzip collagen-quant.tar
```

**2. Transfer the tar file to your cluster**:

```bash
# Using scp
scp collagen-quant.tar.gz username@cluster.edu:/scratch/$USER/

# Or using rsync (better for large files)
rsync -avP collagen-quant.tar.gz username@cluster.edu:/scratch/$USER/
```

**3. On the cluster**, convert the tar archive to SIF:

```bash
# Using Apptainer
apptainer build collagen-quant.sif docker-archive://collagen-quant.tar.gz

# Or using Singularity (older systems)
singularity build collagen-quant.sif docker-archive://collagen-quant.tar.gz

# Clean up the tar file after conversion
rm collagen-quant.tar.gz
```

### Running with Apptainer/Singularity

```bash
# Interactive shell
apptainer shell \
  --bind /path/to/data:/data \
  collagen-quant.sif

# Inside the container
pixi shell
pixi run decon

# Execute command directly
apptainer exec \
  --bind /path/to/raw_images:/data/input \
  --bind /path/to/output:/data/output \
  collagen-quant.sif \
  pixi run decon

# Run with GPU support (if needed in future)
apptainer exec --nv \
  --bind /path/to/data:/data \
  collagen-quant.sif \
  pixi run seg
```

### HPC Job Scheduler (SLURM Example)

```bash
#!/bin/bash
#SBATCH --job-name=collagen-quant
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00

# Load Apptainer module (if required by your HPC)
module load apptainer

# Run processing workflow
apptainer exec \
  --bind /scratch/$USER/histology_data:/data \
  /path/to/collagen-quant.sif \
  bash -c "pixi shell && pixi run decon && pixi run seg"
```

## Docker Compose (Advanced)

For more complex setups with multiple services:

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  collagen-quant:
    build: .
    image: collagen-quant:latest
    volumes:
      - ./raw_images:/data/input
      - ./processed_data:/data/output
      - ./notebook:/app/notebook
    ports:
      - "8888:8888"
    command: pixi run notebook
    environment:
      - JUPYTER_ENABLE_LAB=yes
    stdin_open: true
    tty: true
```

Run with:
```bash
docker-compose up
```

## Best Practices for Docker Usage

### 1. Data Management

- ✅ Always use volume mounts (`-v`) for data directories
- ❌ Never store important data inside containers
- ✅ Use consistent mount points like `/data/input` and `/data/output`

### 2. Resource Limits

```bash
docker run -it --rm \
  --cpus="8" \
  --memory="32g" \
  -v /path/to/data:/data \
  collagen-quant
```

### 3. Persistence

- Results are saved to mounted volumes and persist after container exits
- The `.pixi` environment is built into the image for faster startup

### 4. Security

Run containers with user permissions:

```bash
docker run -it --rm \
  --user $(id -u):$(id -g) \
  -v /path/to/data:/data \
  collagen-quant
```

For read-only filesystems:

```bash
docker run -it --rm \
  --read-only \
  --tmpfs /tmp \
  -v /path/to/data:/data \
  collagen-quant
```

### 5. Multi-platform Builds

Build for multiple architectures:

```bash
# Enable buildx (if not already enabled)
docker buildx create --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t collagen-quant:latest \
  --push .
```

## Troubleshooting

### Container won't start

```bash
# Check if image exists
docker images | grep collagen-quant

# Check container logs
docker logs <container_id>

# Run with verbose output
docker run -it --rm collagen-quant bash
```

### Volume mounting issues

```bash
# Verify paths exist
ls /path/to/your/data

# Check permissions
ls -la /path/to/your/data

# Use absolute paths (not relative)
docker run -it --rm \
  -v $(pwd)/data:/data \
  collagen-quant
```

### Out of disk space

```bash
# Clean up old images and containers
docker system prune -a

# Remove specific image
docker rmi collagen-quant:old-tag
```

### Build fails with git errors

See [Building for Private Repositories](#for-private-github-repositories) section above.

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Apptainer Documentation](https://apptainer.org/docs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Back to Installation Guide](installation.md)
- [Back to Main README](../README.MD)
