"""Tests for the staging Secrets Manager ARN preflight script."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/validate-staging-secret-arns.sh"
ACCOUNT = "758248541054"
REGION = "ap-southeast-1"
ACTIVE_SECRET_AWS_SCRIPT = """
for ((index = 1; index <= $#; index++)); do
  if [[ ${!index} == "--secret-id" ]]; then
    next_index=$((index + 1))
    secret_id=${!next_index}
  fi
done
if [[ "$*" == *"--query ARN"* ]]; then echo "$secret_id"; else echo None; fi
"""


def secret_arn(name: str) -> str:
    return f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:{name}-AbCdEf"


def run_preflight(
    tmp_path: Path, aws_script: str, **overrides: str
) -> subprocess.CompletedProcess[str]:
    aws = tmp_path / "aws"
    aws.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{aws_script}\n")
    aws.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "AWS_REGION": REGION,
        "AWS_ACCOUNT_ID": ACCOUNT,
        "APPLICATION_SECRET_ARN": secret_arn("application"),
        "RECOVERY_SECRET_ARN": secret_arn("recovery"),
        "NUTRITION_SECRET_ARN": secret_arn("nutrition"),
        "TRAINING_SECRET_ARN": secret_arn("training"),
        "REDIS_AUTH_TOKEN_SECRET_ARN": secret_arn("redis-auth-token"),
        **overrides,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )


def test_preflight_accepts_active_complete_secret_arns(tmp_path: Path):
    result = run_preflight(
        tmp_path,
        ACTIVE_SECRET_AWS_SCRIPT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("is a valid active staging secret ARN.") == 5


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("NUTRITION_SECRET_ARN", "nutrition-name-only"),
        ("NUTRITION_SECRET_ARN", secret_arn("nutrition").replace(REGION, "us-east-1")),
        (
            "NUTRITION_SECRET_ARN",
            secret_arn("nutrition").replace(ACCOUNT, "000000000000"),
        ),
        ("NUTRITION_SECRET_ARN", f"{secret_arn('nutrition')}:json-key"),
        ("REDIS_AUTH_TOKEN_SECRET_ARN", "redis-auth-token-name-only"),
    ],
)
def test_preflight_rejects_malformed_or_wrong_scope_arns(
    tmp_path: Path, variable: str, value: str
):
    result = run_preflight(tmp_path, ACTIVE_SECRET_AWS_SCRIPT, **{variable: value})

    assert result.returncode != 0
    assert f"{variable} must be a complete Secrets Manager ARN" in result.stderr
    assert value not in result.stderr


def test_preflight_reports_secret_that_cannot_be_described(tmp_path: Path):
    result = run_preflight(
        tmp_path, 'if [[ "$*" == *"--query ARN"* ]]; then exit 254; fi; echo None'
    )

    assert result.returncode != 0
    assert "APPLICATION_SECRET_ARN could not be described" in result.stderr


@pytest.mark.parametrize(
    ("aws_error", "expected_message"),
    [
        (
            "An error occurred (AccessDeniedException) when calling the DescribeSecret operation: User is not authorized",
            "The deployment role is not authorized to describe APPLICATION_SECRET_ARN",
        ),
        (
            "An error occurred (ResourceNotFoundException) when calling the DescribeSecret operation: Secret was not found.",
            "APPLICATION_SECRET_ARN does not identify an existing secret",
        ),
    ],
)
def test_preflight_categorizes_describe_secret_failures_without_exposing_arn(
    tmp_path: Path, aws_error: str, expected_message: str
):
    result = run_preflight(
        tmp_path,
        f"""if [[ "$*" == *"--query ARN"* ]]; then
  echo '{aws_error}' >&2
  exit 254
fi
echo None
""",
    )

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert secret_arn("application") not in result.stdout
    assert secret_arn("application") not in result.stderr


def test_preflight_rejects_secret_scheduled_for_deletion(tmp_path: Path):
    result = run_preflight(
        tmp_path,
        """
for ((index = 1; index <= $#; index++)); do
  if [[ ${!index} == "--secret-id" ]]; then
    next_index=$((index + 1))
    secret_id=${!next_index}
  fi
done
if [[ "$*" == *"--query ARN"* ]]; then echo "$secret_id"; else echo "2026-11-10T00:00:00+00:00"; fi
""",
    )

    assert result.returncode != 0
    assert (
        "APPLICATION_SECRET_ARN refers to a secret scheduled for deletion."
        in result.stderr
    )
