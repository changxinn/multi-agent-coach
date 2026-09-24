from pathlib import Path


def test_nutrition_agent_repository_never_queries_main_application_schema():
    repository = (
        Path(__file__).parents[1]
        / "services"
        / "nutrition_agent"
        / "app"
        / "repository.py"
    )

    assert "systemdb." not in repository.read_text(encoding="utf-8")
