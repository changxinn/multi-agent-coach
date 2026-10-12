#!/usr/bin/env bash
# Run migration task definitions sequentially and fail deployment if any task exits non-zero.
set -euo pipefail
: "${AWS_REGION:?AWS_REGION is required}"
: "${STACK_NAME:?STACK_NAME is required}"

output() { aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text; }
cluster=$(output ClusterName)
subnets=$(output PrivateSubnetIds)
security_group=$(output TaskSecurityGroupId)
if [[ ${SEED_DEMO_USERS:-false} == true ]]; then
  python -c 'import os; p=os.environ.get("STAGING_DEMO_PASSWORD", ""); assert p and len(p.encode("utf-8")) <= 72, "STAGING_DEMO_PASSWORD must contain 1 to 72 UTF-8 bytes"'
fi
for task_key in ${MIGRATION_TASK_OUTPUTS:-ApiMigrationTaskDefinitionArn RecoveryMigrationTaskDefinitionArn NutritionMigrationTaskDefinitionArn TrainingMigrationTaskDefinitionArn}; do
  task_definition=$(output "$task_key")
  if [[ $task_key == ApiMigrationTaskDefinitionArn && ${SEED_DEMO_USERS:-false} == true ]]; then
    task_arn=$(python scripts/run-api-migration-task.py "$cluster" "$task_definition" "$subnets" "$security_group")
  else
    task_arn=$(aws ecs run-task --region "$AWS_REGION" --cluster "$cluster" --launch-type FARGATE --task-definition "$task_definition" --network-configuration "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$security_group],assignPublicIp=DISABLED}" --query 'tasks[0].taskArn' --output text)
  fi
  [[ -n $task_arn && $task_arn != None ]] || { echo "ECS did not start $task_key" >&2; exit 1; }
  aws ecs wait tasks-stopped --region "$AWS_REGION" --cluster "$cluster" --tasks "$task_arn"
  exit_code=$(aws ecs describe-tasks --region "$AWS_REGION" --cluster "$cluster" --tasks "$task_arn" --query 'tasks[0].containers[0].exitCode' --output text)
  [[ "$exit_code" == "0" ]] || { echo "Migration failed: $task_key (exit $exit_code)" >&2; exit 1; }
done