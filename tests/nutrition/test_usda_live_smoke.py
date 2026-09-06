"""Opt-in USDA smoke coverage; never logs the local API key or full payload."""

from __future__ import annotations

import os

import pytest

from services.nutrition_agent.app.tools.food_database import FoodDatabaseClient


@pytest.mark.asyncio
async def test_live_usda_search_returns_normalized_records() -> None:
    """Run only with explicit operator intent and a locally supplied USDA key."""
    if os.environ.get("NUTRITION_RUN_LIVE_USDA_TESTS") != "1":
        pytest.skip("set NUTRITION_RUN_LIVE_USDA_TESTS=1 to run live USDA smoke")
    api_key = os.environ.get("USDA_FDC_API_KEY")
    if not api_key:
        pytest.skip("USDA_FDC_API_KEY is not configured")

    foods = await FoodDatabaseClient(api_key).search_and_get_details("oats", 1)

    assert foods
    assert isinstance(foods[0]["fdc_id"], int)
    assert foods[0]["name"]