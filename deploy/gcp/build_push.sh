#!/usr/bin/env bash
# Build and push the production images to Artifact Registry (linux/amd64).
set -euo pipefail

PROJECT_ID="${1:?usage: build_push.sh PROJECT_ID [REGION] [TAG]}"
REGION="${2:-us-central1}"
TAG="${3:-latest}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/congress"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

docker buildx build --platform linux/amd64 -f Dockerfile.prod \
  -t "${REGISTRY}/backend:${TAG}" --push .
docker buildx build --platform linux/amd64 -f frontend/app/Dockerfile.prod \
  -t "${REGISTRY}/frontend:${TAG}" --push frontend/app
