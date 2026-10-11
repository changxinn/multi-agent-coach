#!/usr/bin/env bash
set -euo pipefail

: "${APPLICATION_AWS_REGION:?APPLICATION_AWS_REGION is required}"
: "${FRONTEND_AWS_REGION:?FRONTEND_AWS_REGION is required}"
: "${APPLICATION_STACK_NAME:?APPLICATION_STACK_NAME is required}"
: "${FRONTEND_STACK_NAME:?FRONTEND_STACK_NAME is required}"
: "${PROJECT_NAME:=macoach}"
: "${ENVIRONMENT:=staging}"

api_alb_dns=$(aws cloudformation describe-stacks --region "$APPLICATION_AWS_REGION" --stack-name "$APPLICATION_STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDnsName'].OutputValue | [0]" --output text)
if [ -z "$api_alb_dns" ] || [ "$api_alb_dns" = "None" ]; then
  echo "LoadBalancerDnsName was not returned by $APPLICATION_STACK_NAME" >&2
  exit 1
fi

export STACK_NAME="$FRONTEND_STACK_NAME"
export TEMPLATE_FILE=infrastructure/cloudformation/frontend.yaml
export PARAMETER_OVERRIDES="ParameterKey=ProjectName,ParameterValue=${PROJECT_NAME} ParameterKey=Environment,ParameterValue=${ENVIRONMENT} ParameterKey=ApiLoadBalancerDnsName,ParameterValue=${api_alb_dns}"
AWS_REGION="$FRONTEND_AWS_REGION" bash scripts/deploy-cloudformation.sh

bucket=$(aws cloudformation describe-stacks --region "$FRONTEND_AWS_REGION" --stack-name "$FRONTEND_STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue | [0]" --output text)
distribution=$(aws cloudformation describe-stacks --region "$FRONTEND_AWS_REGION" --stack-name "$FRONTEND_STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue | [0]" --output text)

npm --prefix frontend ci
VITE_API_BASE_URL=/api npm --prefix frontend run build
aws s3 sync frontend/dist/ "s3://${bucket}/" --delete --region "$FRONTEND_AWS_REGION"
aws cloudfront create-invalidation --region "$FRONTEND_AWS_REGION" --distribution-id "$distribution" --paths '/*' >/dev/null
