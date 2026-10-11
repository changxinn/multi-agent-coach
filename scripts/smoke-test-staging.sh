#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${STACK_NAME:?STACK_NAME is required}"

frontend_url=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue | [0]" --output text)
health_url=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='ApiHealthUrl'].OutputValue | [0]" --output text)
if [[ -z $frontend_url || $frontend_url == "None" ]]; then
  echo "FrontendUrl was not returned by $STACK_NAME" >&2
  exit 1
fi
if [[ -z $health_url || $health_url == "None" ]]; then
  echo "ApiHealthUrl was not returned by $STACK_NAME" >&2
  exit 1
fi

for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error "$frontend_url" >/dev/null \
    && curl --fail --silent --show-error "$health_url" >/dev/null; then
    echo "Staging frontend and API health checks succeeded: $frontend_url, $health_url"
    exit 0
  fi
  sleep 10
done

echo "Staging frontend or API health check failed: $frontend_url, $health_url" >&2
exit 1
