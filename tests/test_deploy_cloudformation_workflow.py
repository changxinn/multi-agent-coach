"""Regression checks for the staging deployment workflow."""

from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github/workflows/deploy-cloudformation.yml"


def test_workflow_reuses_preprovisioned_ecr_repositories():
    workflow = WORKFLOW.read_text()

    assert "REGISTRY_STACK_NAME" not in workflow
    assert "Deploy ECR repositories" not in workflow
    assert "infrastructure/cloudformation/registry.yaml" not in workflow
    assert "Build and push service images" in workflow


def test_workflow_shows_events_after_failed_first_stack_create():
    workflow = WORKFLOW.read_text()

    assert "if: ${{ failure() }}" in workflow
    assert "steps.stack.outputs.exists == 'true'" not in workflow
    assert '|| echo "No staging stack events are available."' in workflow


def test_workflow_deploys_frontend_to_the_application_alb():
    workflow = WORKFLOW.read_text()

    assert "APPLICATION_AWS_REGION: ap-southeast-1" in workflow
    assert "FRONTEND_AWS_REGION" not in workflow
    assert "FRONTEND_STACK_NAME" not in workflow
    assert "deploy-frontend.sh" not in workflow
    assert (
        workflow.count(
            "ParameterKey=FrontendImage,ParameterValue=${{ steps.images.outputs.FRONTEND_IMAGE }}"
        )
        == 2
    )
    assert "Smoke test frontend and API" in workflow


def test_workflow_deploys_only_after_ci_succeeds_on_the_tested_revision():
    workflow = WORKFLOW.read_text()

    assert (
        'workflow_run:\n    workflows: ["CI"]\n    types: [completed]\n    branches: [main]'
        in workflow
    )
    assert "push:" not in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert (
        "github.event.workflow_run.head_repository.full_name == github.repository"
        in workflow
    )
    assert "github.event.workflow_run.head_sha" in workflow
    assert "ref: ${{ env.DEPLOY_REF }}" in workflow
