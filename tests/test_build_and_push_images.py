"""Tests for idempotent ECR image publishing."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/build-and-push-images.sh"
SERVICES = (
    "frontend",
    "api",
    "recovery-agent",
    "head-coach",
    "summarizer",
    "nutrition-agent",
    "training-agent",
    "database-bootstrap",
)


def run_image_script(tmp_path: Path, describe_behavior: str):
    calls = tmp_path / "calls"
    state = tmp_path / "state"
    aws = tmp_path / "aws"
    docker = tmp_path / "docker"
    output = tmp_path / "github-output"
    aws.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
case "$2" in
  get-login-password) printf 'password' ;;
  describe-images)
    printf '%s\\n' "$*" >> "$CALLS"
    {describe_behavior}
    ;;
  *) echo "Unexpected AWS command: $*" >&2; exit 74 ;;
esac
"""
    )
    docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
cat >/dev/null
printf '%s\\n' "$*" >> "$CALLS"
"""
    )
    aws.chmod(0o755)
    docker.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CALLS": str(calls),
        "STATE": str(state),
        "GITHUB_OUTPUT": str(output),
        "AWS_REGION": "ap-southeast-1",
        "AWS_ACCOUNT_ID": "758248541054",
        "IMAGE_TAG": "commit-sha",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )
    return (
        result,
        calls.read_text() if calls.exists() else "",
        output.read_text() if output.exists() else "",
    )


def test_reuses_existing_immutable_ecr_images_without_building_or_pushing(
    tmp_path: Path,
):
    result, calls, output = run_image_script(
        tmp_path, "printf 'sha256:existing'\n    exit 0"
    )

    assert result.returncode == 0
    assert calls.count("describe-images") == len(SERVICES)
    assert "build" not in calls
    assert "push" not in calls
    assert output.count("@sha256:existing") == len(SERVICES)


def test_builds_and_pushes_only_when_ecr_tag_does_not_exist(tmp_path: Path):
    result, calls, output = run_image_script(
        tmp_path,
        """count=$(cat "$STATE" 2>/dev/null || printf '0')
    count=$((count + 1))
    printf '%s' "$count" > "$STATE"
    if [ $((count % 2)) -eq 1 ]; then
      echo 'An error occurred (ImageNotFoundException)' >&2
      exit 255
    fi
    printf 'sha256:created'
    """,
    )

    assert result.returncode == 0
    assert calls.count("describe-images") == len(SERVICES) * 2
    assert calls.count("build --pull") == len(SERVICES)
    assert calls.count("push ") == len(SERVICES)
    assert output.count("@sha256:created") == len(SERVICES)
    assert "--build-arg VITE_API_BASE_URL=/api" in calls


def test_stops_on_ecr_lookup_errors_other_than_missing_image(tmp_path: Path):
    result, calls, output = run_image_script(
        tmp_path,
        "echo 'An error occurred (AccessDeniedException)' >&2; exit 255",
    )

    assert result.returncode == 1
    assert "Could not determine whether immutable image tag" in result.stderr
    assert "AccessDeniedException" in result.stderr
    assert calls.count("describe-images") == 1
    assert "build" not in calls
    assert output == ""
