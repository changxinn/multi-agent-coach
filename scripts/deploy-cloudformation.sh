#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${STACK_NAME:?STACK_NAME is required}"
: "${TEMPLATE_FILE:?TEMPLATE_FILE is required}"
: "${PARAMETER_OVERRIDES:?PARAMETER_OVERRIDES is required}"

aws cloudformation validate-template --region "$AWS_REGION" --template-body "file://${TEMPLATE_FILE}" >/dev/null

change_set_name="github-${GITHUB_RUN_ID:-local}-$(date +%s)"
if stack_status=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' \
  --output text 2>&1); then
  if [[ $stack_status == REVIEW_IN_PROGRESS ]]; then
    printf 'Stack %s is in REVIEW_IN_PROGRESS. Delete the unexecuted review stack or execute its CREATE change set before retrying.\n' "$STACK_NAME" >&2
    exit 1
  fi
  if [[ $stack_status == ROLLBACK_COMPLETE ]]; then
    echo "Deleting failed stack ${STACK_NAME} before recreating it."
    aws cloudformation delete-stack --region "$AWS_REGION" --stack-name "$STACK_NAME"
    aws cloudformation wait stack-delete-complete --region "$AWS_REGION" --stack-name "$STACK_NAME"
    change_set_type=CREATE
    stack_waiter=stack-create-complete
  else
    change_set_type=UPDATE
    stack_waiter=stack-update-complete
  fi
elif [[ $stack_status == *"does not exist"* ]]; then
  change_set_type=CREATE
  stack_waiter=stack-create-complete
else
  printf 'Could not determine whether stack %s exists:\n%s\n' "$STACK_NAME" "$stack_status" >&2
  exit 1
fi

echo "Creating ${change_set_type} change set for stack ${STACK_NAME}."

aws cloudformation create-change-set \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --change-set-name "$change_set_name" \
  --change-set-type "$change_set_type" \
  --template-body "file://${TEMPLATE_FILE}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters $PARAMETER_OVERRIDES >/dev/null

set +e
aws cloudformation wait change-set-create-complete --region "$AWS_REGION" --stack-name "$STACK_NAME" --change-set-name "$change_set_name"
wait_status=$?
set -e
if [ "$wait_status" -ne 0 ]; then
  change_set_details=$(aws cloudformation describe-change-set \
    --region "$AWS_REGION" \
    --stack-name "$STACK_NAME" \
    --change-set-name "$change_set_name" \
    --query '{Id:ChangeSetId,Status:Status,ExecutionStatus:ExecutionStatus,StatusReason:StatusReason}' \
    --output json 2>&1) || {
      printf 'Change set %s failed and CloudFormation could not return its details:\n%s\n' "$change_set_name" "$change_set_details" >&2
      exit "$wait_status"
    }
  reason=$(aws cloudformation describe-change-set --region "$AWS_REGION" --stack-name "$STACK_NAME" --change-set-name "$change_set_name" --query StatusReason --output text)
  if grep -q 'didn.t contain changes' <<<"$reason"; then
    echo "No infrastructure changes for $STACK_NAME."
    exit 0
  fi
  printf 'CloudFormation change set %s failed:\n%s\n' "$change_set_name" "$change_set_details" >&2
  exit "$wait_status"
fi

aws cloudformation describe-change-set --region "$AWS_REGION" --stack-name "$STACK_NAME" --change-set-name "$change_set_name" --query 'Changes[].ResourceChange.[Action,LogicalResourceId,ResourceType]' --output table
aws cloudformation execute-change-set --region "$AWS_REGION" --stack-name "$STACK_NAME" --change-set-name "$change_set_name"
aws cloudformation wait "$stack_waiter" --region "$AWS_REGION" --stack-name "$STACK_NAME"
aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs' --output table
