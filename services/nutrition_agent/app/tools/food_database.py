"""USDA FoodData Central API client with local cache fallback."""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class FoodDatabaseClient:
    """Client for USDA FoodData Central API."""

    def __init__(self, api_key: str, base_url: str = "https://api.nal.usda.gov/fdc/v1"):
        """
        Initialize USDA FoodData Central client.

        Args:
            api_key: USDA FDC API key
            base_url: API base URL
        """
        self.api_key = api_key
        self.base_url = base_url

    async def search_food(
        self,
        query: str,
        data_type: str = "Foundation",
        page_size: int = 10,
    ) -> list[dict]:
        """
        Search for foods by keyword.

        Args:
            query: Search keyword (e.g., "chicken breast")
            data_type: One of: Foundation, SR Legacy, Survey, Branded, Experimental
            page_size: Number of results (max 50)

        Returns:
            List of foods with basic info: [{fdc_id, name, brand, ...}]
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/foods/search",
                    params={
                        "api_key": self.api_key,
                        "query": query,
                        "dataType": [data_type] if isinstance(data_type, str) else data_type,
                        "pageSize": min(page_size, 50),
                    },
                )
                response.raise_for_status()
                data = response.json()

                foods = []
                for food in data.get("foods", []):
                    foods.append({
                        "fdc_id": food.get("fdcId"),
                        "name": food.get("description"),
                        "brand": food.get("brandOwner"),
                        "food_category": food.get("foodCategory"),
                    })

                return foods

        except httpx.HTTPError as e:
            logger.warning(f"USDA API search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"USDA API search error: {e}")
            return []

    async def get_food_details(self, fdc_id: int) -> Optional[dict]:
        """
        Get detailed nutrition info for a food by FDC ID.

        Args:
            fdc_id: USDA FoodData Central food ID

        Returns:
            dict with nutrition info per 100g serving, or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/food/{fdc_id}",
                    params={
                        "api_key": self.api_key,
                        "nutrients": [
                            "1003",  # Protein (g)
                            "1005",  # Carbohydrate (g)
                            "1004",  # Fat (g)
                            "1008",  # Energy (kcal)
                            "1079",  # Fiber, total dietary (g)
                        ],
                    },
                )
                response.raise_for_status()
                food = response.json()

                # Extract nutrients
                nutrients = {n["nutrient"]["id"]: n["amount"] for n in food.get("foodNutrients", [])}

                return {
                    "fdc_id": food.get("fdcId"),
                    "name": food.get("description"),
                    "brand": food.get("brandOwner"),
                    "serving_size_g": food.get("servingSize", 100),
                    "calories": nutrients.get(1008, 0),
                    "protein_g": nutrients.get(1003, 0),
                    "carbs_g": nutrients.get(1005, 0),
                    "fat_g": nutrients.get(1004, 0),
                    "fiber_g": nutrients.get(1079),
                    "food_category": food.get("foodCategory"),
                }

        except httpx.HTTPError as e:
            logger.warning(f"USDA API details failed for {fdc_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"USDA API details error: {e}")
            return None

    async def search_and_get_details(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search for foods and get detailed nutrition info.

        Args:
            query: Search keyword
            max_results: Maximum number of detailed results to return

        Returns:
            List of foods with full nutrition info
        """
        search_results = await self.search_food(query, page_size=max_results)
        detailed_foods = []

        for food in search_results[:max_results]:
            fdc_id = food.get("fdc_id")
            if fdc_id:
                details = await self.get_food_details(fdc_id)
                if details:
                    detailed_foods.append(details)

        return detailed_foods
