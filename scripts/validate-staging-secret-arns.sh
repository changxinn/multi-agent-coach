#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required}"
: "${APPLICATION_SECRET_ARN:?APPLICATION_SECRET_ARN is required}"
: "${RECOVERY_SECRET_ARN:?RECOVERY_SECRET_ARN is required}"
: "${NUTRITION_SECRET_ARN:?NUTRITION_SECRET_ARN is required}"
: "${TRAINING_SECRET_ARN:?TRAINING_SECRET_ARN is required}"
: "${REDIS_AUTH_TOKEN_SECRET_ARN:?REDIS_AUTH_TOKEN_SECRET_ARN is required}"

expected_prefix="arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:"

validate_secret() {
  local variable_name=$1
  local secret_arn=$2
  local resolved_arn
  local deleted_date
  local describe_error

  if [[ $secret_arn != "${expected_prefix}"* ]] || [[ ${secret_arn#"${expected_prefix}"} == "$secret_arn" ]] || [[ ${secret_arn#"${expected_prefix}"} == *:* ]]; then
    echo "::error::${variable_name} must be a complete Secrets Manager ARN in AWS account ${AWS_ACCOUNT_ID} and region ${AWS_REGION}." >&2
    return 1
  fi

  if ! resolved_arn=$(aws secretsmanager describe-secret \
    --region "$AWS_REGION" \
    --secret-id "$secret_arn" \
    --query ARN \
    --output text 2>&1); then
    describe_error=$resolved_arn
    if [[ $describe_error == *AccessDenied* || $describe_error == *Unauthorized* ]]; then
      echo "::error::The deployment role is not authorized to describe ${variable_name} in AWS account ${AWS_ACCOUNT_ID} and region ${AWS_REGION}. Grant secretsmanager:DescribeSecret on the runtime secret." >&2
    elif [[ $describe_error == *ResourceNotFoundException* ]]; then
      echo "::error::${variable_name} does not identify an existing secret in AWS account ${AWS_ACCOUNT_ID} and region ${AWS_REGION}." >&2
    else
      echo "::error::${variable_name} could not be described by the deployment role in AWS account ${AWS_ACCOUNT_ID} and region ${AWS_REGION}." >&2
    fi
    return 1
  fi

  if [[ $resolved_arn != "$secret_arn" ]]; then
    echo "::error::${variable_name} did not resolve to the supplied complete secret ARN." >&2
    return 1
  fi

  if ! deleted_date=$(aws secretsmanager describe-secret \
    --region "$AWS_REGION" \
    --secret-id "$secret_arn" \
    --query DeletedDate \
    --output text 2>/dev/null); then
    echo "::error::${variable_name} could not be checked for scheduled deletion." >&2
    return 1
  fi
  if [[ $deleted_date != "None" && $deleted_date != "null" && -n $deleted_date ]]; then
    echo "::error::${variable_name} refers to a secret scheduled for deletion." >&2
    return 1
  fi

  echo "${variable_name} is a valid active staging secret ARN."
}

validate_secret APPLICATION_SECRET_ARN "$APPLICATION_SECRET_ARN"
validate_secret RECOVERY_SECRET_ARN "$RECOVERY_SECRET_ARN"
validate_secret NUTRITION_SECRET_ARN "$NUTRITION_SECRET_ARN"
validate_secret TRAINING_SECRET_ARN "$TRAINING_SECRET_ARN"
validate_secret REDIS_AUTH_TOKEN_SECRET_ARN "$REDIS_AUTH_TOKEN_SECRET_ARN"