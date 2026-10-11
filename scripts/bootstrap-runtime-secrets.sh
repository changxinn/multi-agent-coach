#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${STACK_NAME:?STACK_NAME is required}"
: "${APPLICATION_SECRET_ARN:?APPLICATION_SECRET_ARN is required}"
: "${NUTRITION_SECRET_ARN:?NUTRITION_SECRET_ARN is required}"

main_endpoint=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='MainDatabaseEndpoint'].OutputValue | [0]" --output text)
nutrition_endpoint=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='NutritionDatabaseEndpoint'].OutputValue | [0]" --output text)
redis_endpoint=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='RedisEndpoint'].OutputValue | [0]" --output text)
main_instance=$(aws cloudformation describe-stack-resources --region "$AWS_REGION" --stack-name "$STACK_NAME" --logical-resource-id MainDatabase --query 'StackResources[0].PhysicalResourceId' --output text)
nutrition_instance=$(aws cloudformation describe-stack-resources --region "$AWS_REGION" --stack-name "$STACK_NAME" --logical-resource-id NutritionDatabase --query 'StackResources[0].PhysicalResourceId' --output text)

main_master_secret=$(aws rds describe-db-instances --region "$AWS_REGION" --db-instance-identifier "$main_instance" --query 'DBInstances[0].MasterUserSecret.SecretArn' --output text)
nutrition_master_secret=$(aws rds describe-db-instances --region "$AWS_REGION" --db-instance-identifier "$nutrition_instance" --query 'DBInstances[0].MasterUserSecret.SecretArn' --output text)
main_password=$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$main_master_secret" --query SecretString --output text | jq -r .password)
nutrition_password=$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$nutrition_master_secret" --query SecretString --output text | jq -r .password)

application_json=$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$APPLICATION_SECRET_ARN" --query SecretString --output text | jq --arg url "postgresql+asyncpg://main_app:${main_password}@${main_endpoint}:5432/systemdb" --arg redis_url "redis://${redis_endpoint}:6379/0" '.DATABASE_URL = $url | .REDIS_URL = $redis_url')
nutrition_json=$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$NUTRITION_SECRET_ARN" --query SecretString --output text | jq --arg url "postgresql://nutrition_agent:${nutrition_password}@${nutrition_endpoint}:5432/nutritiondb" '.NUTRITION_DATABASE_URL = $url')

aws secretsmanager put-secret-value --region "$AWS_REGION" --secret-id "$APPLICATION_SECRET_ARN" --secret-string "$application_json" >/dev/null
aws secretsmanager put-secret-value --region "$AWS_REGION" --secret-id "$NUTRITION_SECRET_ARN" --secret-string "$nutrition_json" >/dev/null
