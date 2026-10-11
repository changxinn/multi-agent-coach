#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required}"
: "${PROJECT_NAME:=macoach}"
: "${ENVIRONMENT:=staging}"
: "${IMAGE_TAG:=${GITHUB_SHA:-$(git rev-parse HEAD)}}"

registry="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$registry"

build_and_push() {
  local service=$1 context=$2 dockerfile=$3
  shift 3
  local image="${registry}/${PROJECT_NAME}-${ENVIRONMENT}/${service}:${IMAGE_TAG}"
  local digest describe_output

  if describe_output=$(aws ecr describe-images \
    --region "$AWS_REGION" \
    --repository-name "${PROJECT_NAME}-${ENVIRONMENT}/${service}" \
    --image-ids "imageTag=${IMAGE_TAG}" \
    --query 'imageDetails[0].imageDigest' \
    --output text 2>&1); then
    digest=$describe_output
    echo "Reusing existing immutable image tag $image."
  elif [[ $describe_output == *ImageNotFoundException* ]]; then
    docker build --pull --file "$dockerfile" "$@" --tag "$image" "$context"
    docker push "$image"
    digest=$(aws ecr describe-images \
      --region "$AWS_REGION" \
      --repository-name "${PROJECT_NAME}-${ENVIRONMENT}/${service}" \
      --image-ids "imageTag=${IMAGE_TAG}" \
      --query 'imageDetails[0].imageDigest' \
      --output text)
  else
    printf 'Could not determine whether immutable image tag %s already exists:\n%s\n' "$image" "$describe_output" >&2
    exit 1
  fi

  [[ "$digest" == sha256:* ]] || { echo "Could not resolve an immutable digest for $image" >&2; exit 1; }
  printf '%s=%s@%s\n' "$(tr '[:lower:]-' '[:upper:]_' <<<"$service")_IMAGE" "${registry}/${PROJECT_NAME}-${ENVIRONMENT}/${service}" "$digest" >> "${GITHUB_OUTPUT:-/dev/stdout}"
}

build_and_push frontend frontend frontend/Dockerfile --build-arg VITE_API_BASE_URL=/api
build_and_push api . Dockerfile
build_and_push recovery-agent . services/recovery_agent/Dockerfile
build_and_push head-coach . services/head_coach/Dockerfile
build_and_push summarizer . services/summarizer/Dockerfile
build_and_push nutrition-agent . services/nutrition_agent/Dockerfile
build_and_push training-agent . services/training_agent/Dockerfile
build_and_push database-bootstrap . services/database_bootstrap/Dockerfile
