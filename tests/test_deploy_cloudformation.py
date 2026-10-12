"""Tests for CloudFormation stack-state selection in the deployment script."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/deploy-cloudformation.sh"


def run_deploy_script(tmp_path: Path, describe_response: str, describe_exit: int = 0):
    calls = tmp_path / "aws-calls"
    aws = tmp_path / "aws"
    aws.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
case "$2" in
  validate-template)
    exit 0
    ;;
  describe-stacks)
    echo '{describe_response}' >&2
    exit {describe_exit}
    ;;
  create-change-set)
    printf '%s\\n' "$*" >> "$AWS_CALLS"
    exit 73
    ;;
  *)
    echo "Unexpected AWS command: $*" >&2
    exit 74
    ;;
esac
"""
    )
    aws.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "AWS_CALLS": str(calls),
        "AWS_REGION": "ap-southeast-1",
        "STACK_NAME": "macoach-staging-registry",
        "TEMPLATE_FILE": "infrastructure/cloudformation/registry.yaml",
        "PARAMETER_OVERRIDES": "ParameterKey=ProjectName,ParameterValue=macoach",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )
    return result, calls.read_text() if calls.exists() else ""


def test_deploy_uses_create_for_an_explicitly_missing_stack(tmp_path: Path):
    result, calls = run_deploy_script(
        tmp_path,
        "An error occurred (ValidationError) when calling the DescribeStacks operation: Stack with id macoach-staging-registry does not exist",
        describe_exit=255,
    )

    assert result.returncode == 73
    assert (
        "Creating CREATE change set for stack macoach-staging-registry."
        in result.stdout
    )
    assert "--change-set-type CREATE" in calls


def test_deploy_uses_update_for_an_existing_stack(tmp_path: Path):
    result, calls = run_deploy_script(tmp_path, "UPDATE_COMPLETE")

    assert result.returncode == 73
    assert (
        "Creating UPDATE change set for stack macoach-staging-registry."
        in result.stdout
    )
    assert "--change-set-type UPDATE" in calls


def test_deploy_refuses_to_update_an_unexecuted_review_stack(tmp_path: Path):
    result, calls = run_deploy_script(tmp_path, "REVIEW_IN_PROGRESS")

    assert result.returncode == 1
    assert "macoach-staging-registry is in REVIEW_IN_PROGRESS" in result.stderr
    assert (
        "Delete the unexecuted review stack or execute its CREATE change set"
        in result.stderr
    )
    assert calls == ""


def test_deploy_recreates_a_rollback_complete_stack(tmp_path: Path):
    calls = tmp_path / "aws-calls"
    aws = tmp_path / "aws"
    aws.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "$2" in
  validate-template)
    exit 0
    ;;
  describe-stacks)
    echo ROLLBACK_COMPLETE
    ;;
  delete-stack|create-change-set)
    printf '%s\\n' "$*" >> "$AWS_CALLS"
    [[ "$2" == delete-stack ]] && exit 0
    exit 73
    ;;
  wait)
    printf '%s\\n' "$*" >> "$AWS_CALLS"
    [[ "$3" == stack-delete-complete ]] && exit 0
    exit 74
    ;;
  *)
    echo "Unexpected AWS command: $*" >&2
    exit 75
    ;;
esac
"""
    )
    aws.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "AWS_CALLS": str(calls),
        "AWS_REGION": "ap-southeast-1",
        "STACK_NAME": "macoach-staging-frontend",
        "TEMPLATE_FILE": "infrastructure/cloudformation/frontend.yaml",
        "PARAMETER_OVERRIDES": "ParameterKey=ProjectName,ParameterValue=macoach",
    }

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )

    assert result.returncode == 73
    assert (
        "Deleting failed stack macoach-staging-frontend before recreating it."
        in result.stdout
    )
    assert (
        "Creating CREATE change set for stack macoach-staging-frontend."
        in result.stdout
    )
    assert calls.read_text().splitlines() == [
        "cloudformation delete-stack --region ap-southeast-1 --stack-name macoach-staging-frontend",
        "cloudformation wait stack-delete-complete --region ap-southeast-1 --stack-name macoach-staging-frontend",
        "cloudformation create-change-set --region ap-southeast-1 --stack-name macoach-staging-frontend"
        " --change-set-name "
        + calls.read_text().split("--change-set-name ")[1].split()[0]
        + " --change-set-type CREATE --template-body file://infrastructure/cloudformation/frontend.yaml"
        " --capabilities CAPABILITY_NAMED_IAM --parameters ParameterKey=ProjectName,ParameterValue=macoach",
    ]


def test_deploy_stops_when_stack_lookup_is_not_authorized(tmp_path: Path):
    result, calls = run_deploy_script(
        tmp_path,
        "An error occurred (AccessDenied) when calling the DescribeStacks operation: User is not authorized",
        describe_exit=255,
    )

    assert result.returncode == 1
    assert (
        "Could not determine whether stack macoach-staging-registry exists"
        in result.stderr
    )
    assert "--change-set-type" not in calls


def test_deploy_refuses_an_update_that_replaces_the_application_alb(tmp_path: Path):
    calls = tmp_path / "aws-calls"
    aws = tmp_path / "aws"
    aws.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$AWS_CALLS"
case "$2" in
  validate-template|create-change-set)
    exit 0
    ;;
  describe-stacks)
    echo UPDATE_COMPLETE
    ;;
  wait)
    [[ "$3" == change-set-create-complete ]] && exit 0
    exit 74
    ;;
  describe-change-set)
    if [[ "$*" == *"length(@)"* ]]; then
      echo 1
    else
      echo '[]'
    fi
    ;;
  execute-change-set)
    echo 'The replacement guard did not stop execution' >&2
    exit 75
    ;;
  *)
    echo "Unexpected AWS command: $*" >&2
    exit 76
    ;;
esac
"""
    )
    aws.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "AWS_CALLS": str(calls),
        "AWS_REGION": "ap-southeast-1",
        "STACK_NAME": "macoach-staging-v2",
        "TEMPLATE_FILE": "infrastructure/cloudformation/staging-v2.yaml",
        "PARAMETER_OVERRIDES": "ParameterKey=ProjectName,ParameterValue=macoach",
    }

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )

    assert result.returncode == 1
    assert "it would replace Alb" in result.stderr
    assert "execute-change-set" not in calls.read_text()
