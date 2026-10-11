#!/usr/bin/env bash
# Run the private database/bootstrap task and fail the deployment on a non-zero exit.
set -euo pipefail
: "${AWS_REGION:?AWS_REGION is required}"
: "${STACK_NAME:?STACK_NAME is required}"

output() {
  aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text
}

cluster=$(output ClusterName)
subnets=$(output PrivateSubnetIds)
security_group=$(output TaskSecurityGroupId)
task_definition=$(output DatabaseBootstrapTaskDefinitionArn)
task_arn=$(aws ecs run-task --region "$AWS_REGION" --cluster "$cluster" --launch-type FARGATE \
  --task-definition "$task_definition" \
  --network-configuration "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$security_group],assignPublicIp=DISABLED}" \
  --query 'tasks[0].taskArn' --output text)
[[ "$task_arn" != "None" ]] || { echo 'ECS did not start the bootstrap task' >&2; exit 1; }
aws ecs wait tasks-stopped --region "$AWS_REGION" --cluster "$cluster" --tasks "$task_arn"
exit_code=$(aws ecs describe-tasks --region "$AWS_REGION" --cluster "$cluster" --tasks "$task_arn" \
  --query 'tasks[0].containers[0].exitCode' --output text)
[[ "$exit_code" == "0" ]] || { echo "Database bootstrap failed (exit $exit_code): $task_arn" >&2; exit 1; }
echo "Database bootstrap completed: $task_arn"