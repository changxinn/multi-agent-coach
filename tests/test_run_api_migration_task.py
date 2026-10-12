"""GitHub-only demo password overrides are scoped to the one-off API task."""

import importlib.util
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "run_api_migration_task", ROOT / "scripts/run-api-migration-task.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize("outcome", ["success", "cli_error", "ecs_failure"])
def test_launch_uses_private_file_and_cleans_up_without_echoing_secret(
    monkeypatch, outcome
):
    password = 'Private "password" with spaces!'
    files = []

    def run(args, **kwargs):
        assert password not in " ".join(args)
        assert args[:3] == ["aws", "ecs", "run-task"]
        path = Path(args[-1].removeprefix("file://"))
        files.append(path)
        payload = json.loads(path.read_text())
        assert payload["overrides"]["containerOverrides"] == [
            {
                "name": "api-migrate",
                "environment": [
                    {"name": "SEED_DEMO_USERS", "value": "true"},
                    {"name": "DEMO_USER_PASSWORD", "value": password},
                ],
            }
        ]
        assert payload["networkConfiguration"]["awsvpcConfiguration"] == {
            "subnets": ["subnet-a", "subnet-b"],
            "securityGroups": ["sg-test"],
            "assignPublicIp": "DISABLED",
        }
        response = (
            {"tasks": [{"taskArn": "arn:task"}], "failures": []}
            if outcome == "success"
            else {"tasks": [], "failures": [{"reason": password}]}
        )
        return CompletedProcess(
            args,
            255 if outcome == "cli_error" else 0,
            stdout=json.dumps(response),
            stderr=password,
        )

    monkeypatch.setattr(launcher.subprocess, "run", run)
    args = (
        "ap-southeast-1",
        "cluster",
        "task-definition",
        "subnet-a,subnet-b",
        "sg-test",
        password,
    )
    if outcome == "success":
        assert launcher.run_task(*args) == "arn:task"
    else:
        with pytest.raises(RuntimeError) as error:
            launcher.run_task(*args)
        assert password not in str(error.value)
    assert files and all(not path.exists() for path in files)


@pytest.mark.parametrize("password", ["", "x" * 73])
def test_invalid_password_is_rejected_before_aws_launch(monkeypatch, password):
    def unexpected(*args, **kwargs):
        raise AssertionError("Must not call AWS")

    monkeypatch.setattr(launcher.subprocess, "run", unexpected)
    with pytest.raises(RuntimeError, match="STAGING_DEMO_PASSWORD"):
        launcher.run_task("region", "cluster", "task", "subnet", "sg", password)


def test_workflow_passes_password_only_to_migrations():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/deploy-cloudformation.yml").read_text()
    )
    steps = workflow["jobs"]["deploy"]["steps"]
    secret_steps = [s for s in steps if "STAGING_DEMO_PASSWORD" in s.get("env", {})]
    assert len(secret_steps) == 1
    assert secret_steps[0]["name"] == "Run ordered ECS migrations"
    assert secret_steps[0]["env"]["SEED_DEMO_USERS"] == "true"
    assert (
        secret_steps[0]["env"]["STAGING_DEMO_PASSWORD"]
        == "${{ secrets.STAGING_DEMO_PASSWORD }}"
    )
    assert "DemoPasswordSecretArn" not in str(workflow)
