"""Launch a one-off API migration with a GitHub-provided demo password."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_task(region, cluster, task_definition, subnets, security_group, password):
    if not password or len(password.encode("utf-8")) > 72:
        raise RuntimeError("STAGING_DEMO_PASSWORD must contain 1 to 72 UTF-8 bytes")
    payload = {
        "cluster": cluster,
        "taskDefinition": task_definition,
        "launchType": "FARGATE",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": subnets.split(","),
                "securityGroups": [security_group],
                "assignPublicIp": "DISABLED",
            }
        },
        "overrides": {
            "containerOverrides": [
                {
                    "name": "api-migrate",
                    "environment": [
                        {"name": "SEED_DEMO_USERS", "value": "true"},
                        {"name": "DEMO_USER_PASSWORD", "value": password},
                    ],
                }
            ]
        },
    }
    # Owner-only temporary JSON avoids exposing credentials in CLI arguments.
    # Environment overrides remain visible in ECS metadata and AWS audit logs.
    fd, filename = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
        result = subprocess.run(
            [
                "aws",
                "ecs",
                "run-task",
                "--region",
                region,
                "--cli-input-json",
                f"file://{filename}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            # Do not echo stderr: request validation can include secret values.
            raise RuntimeError("ECS could not launch the API migration task")
        response = json.loads(result.stdout)
        if response.get("failures") or not response.get("tasks"):
            raise RuntimeError("ECS did not start the API migration task")
        return response["tasks"][0]["taskArn"]
    finally:
        Path(filename).unlink(missing_ok=True)


if __name__ == "__main__":
    print(
        run_task(
            os.environ["AWS_REGION"],
            *sys.argv[1:],
            os.environ.get("STAGING_DEMO_PASSWORD", ""),
        )
    )
