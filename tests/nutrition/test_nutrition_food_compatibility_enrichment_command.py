import importlib.util
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def load_command_module():
    script_path = (
        Path(__file__).parents[2] / "scripts/enrich_nutrition_food_compatibility.py"
    )
    spec = importlib.util.spec_from_file_location(
        "compatibility_enrichment_command", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load compatibility enrichment command")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def food(**overrides):
    return {
        "id": 12,
        "provider": "usda",
        "provider_food_id": "321360",
        "description": "Tomatoes, red, ripe, raw, year round average",
        "raw_response": {"fdcId": 321360},
        "input_fingerprint": None,
        "review_status": None,
        **overrides,
    }


def args(**overrides):
    values = {
        "apply": False,
        "force": False,
        "provider": "usda",
        "resume_after_id": 0,
        "batch_size": 25,
        "report": None,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.asyncio
async def test_dry_run_reports_candidates_without_writing(monkeypatch):
    command = load_command_module()
    connection = AsyncMock()
    monkeypatch.setattr(command, "fetch_foods", AsyncMock(return_value=[food()]))
    upsert = AsyncMock()
    monkeypatch.setattr(command, "upsert_candidate", upsert)

    report = await command.enrich(args(), connection)

    assert report["summary"] == {"considered": 1, "written": 0, "skipped_unchanged": 0}
    assert report["records"][0]["outcome"] == "dry_run"
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrichment_skips_unchanged_input_unless_forced(monkeypatch):
    command = load_command_module()
    initial_food = food()
    candidate = command.classify_food_for_review(initial_food)
    monkeypatch.setattr(
        command,
        "fetch_foods",
        AsyncMock(return_value=[food(input_fingerprint=candidate.input_fingerprint)]),
    )
    upsert = AsyncMock(return_value=True)
    monkeypatch.setattr(command, "upsert_candidate", upsert)

    report = await command.enrich(args(apply=True), AsyncMock())

    assert report["records"][0]["outcome"] == "skipped_unchanged"
    upsert.assert_not_awaited()

    report = await command.enrich(args(apply=True, force=True), AsyncMock())
    assert report["records"][0]["outcome"] == "written"
    upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_reports_protected_approved_row_when_upsert_loses_race(monkeypatch):
    command = load_command_module()
    monkeypatch.setattr(command, "fetch_foods", AsyncMock(return_value=[food()]))
    monkeypatch.setattr(command, "upsert_candidate", AsyncMock(return_value=False))

    report = await command.enrich(args(apply=True), AsyncMock())

    assert report["records"][0]["outcome"] == "protected_approved"
    assert report["summary"]["written"] == 0


def test_argument_validation_rejects_invalid_batch_size():
    command = load_command_module()

    with pytest.raises(SystemExit):
        command.parse_args(["--batch-size", "0"])
