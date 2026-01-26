#!/bin/bash
set -e

echo ">>> Starting Murmur Server Setup..."

# 0. Upload Database (if present locally)
if [ -f "murmur.sqlite" ]; then
    echo ">>> Database found! It will be used by the container (ensure it's in the same dir)."
fi

# 1. Update System
echo ">>> Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker (if not found)
if ! command -v docker &> /dev/null; then
    echo ">>> Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo ">>> Docker installed."
else
    echo ">>> Docker is already installed."
fi

# 3. Install Docker Compose (if not found - usually included in modern docker)
if ! command -v docker-compose &> /dev/null; then
     echo ">>> Installing Docker Compose Plugin..."
     sudo apt-get install -y docker-compose-plugin
fi

# 4. Deploy
echo ">>> Building and Starting Murmur Container..."
# Ensure we are in the directory with docker-compose.yml
# If this script is outside, adjust path accordingly.
sudo docker compose up -d --build

echo ">>> Deployment Complete!"
echo ">>> Status:"
sudo docker compose ps
