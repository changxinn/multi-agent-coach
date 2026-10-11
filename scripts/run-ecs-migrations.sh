#!/usr/bin/env bash
# Run migration task definitions sequentially and fail deployment if any task exits non-zero.
set -euo pipefail
: "${AWS_REGION:?AWS_REGION is required}"
: "${STACK_NAME:?STACK_NAME is required}"

output() { aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text; }
cluster=$(output ClusterName)
subnets=$(output PrivateSubnetIds)
security_group=$(output TaskSecurityGroupId)
for task_key in ${MIGRATION_TASK_OUTPUTS:-ApiMigrationTaskDefinitionArn RecoveryMigrationTaskDefinitionArn NutritionMigrationTaskDefinitionArn TrainingMigrationTaskDefinitionArn}; do
  task_definition=$(output "$task_key")
  task_arn=$(aws ecs run-task --region "$AWS_REGION" --cluster "$cluster" --launch-type FARGATE --task-definition "$task_definition" --network-configuration "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$security_group],assignPublicIp=DISABLED}" --query 'tasks[0].taskArn' --output text)
  aws ecs wait tasks-stopped --region "$AWS_REGION" --cluster "$cluster" --tasks "$task_arn"
  exit_code=$(aws ecs describe-tasks --region "$AWS_REGION" --cluster "$cluster" --tasks "$task_arn" --query 'tasks[0].containers[0].exitCode' --output text)
  [[ "$exit_code" == "0" ]] || { echo "Migration failed: $task_key (exit $exit_code)" >&2; exit 1; }
done