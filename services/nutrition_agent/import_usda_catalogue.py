"""Import approved USDA datasets into the Nutrition-owned local food catalogue.

Run from the repository root with the Nutrition Agent environment configured:

PYTHONPATH=services/nutrition_agent .venv/bin/python \
  services/nutrition_agent/import_usda_catalogue.py --all
"""

import argparse
import asyncio

from app.food_data.usda import FoodDataProviderError, UsdaFoodDataCentralProvider
from app.repository import NutritionRepository

from app import database
from app.config import settings

APPROVED_DATA_TYPES = ["Foundation", "SR Legacy", "Survey (FNDDS)"]


async def import_catalogue(page_size: int, max_pages: int | None) -> tuple[int, int]:
    if not settings.USDA_FDC_API_KEY:
        raise RuntimeError("USDA_FDC_API_KEY is required to import the USDA catalogue")

    session_factory = database._session_factory()
    imported = 0
    skipped = 0
    provider = UsdaFoodDataCentralProvider(settings.USDA_FDC_API_KEY)
    try:
        page_number = 1
        while max_pages is None or page_number <= max_pages:
            foods = await provider.list_foods(
                page_number, page_size, APPROVED_DATA_TYPES
            )
            if not foods:
                break
            async with session_factory() as session:
                repo = NutritionRepository(session)
                for food in foods:
                    if None in (
                        food.calories_per_100g,
                        food.protein_g_per_100g,
                        food.carbohydrate_g_per_100g,
                        food.fat_g_per_100g,
                    ):
                        skipped += 1
                        continue
                    await repo.cache_food(food.__dict__)
                    imported += 1
                await session.commit()
            print(f"Imported page {page_number}: {imported} usable foods so far")
            if len(foods) < page_size:
                break
            page_number += 1
    except FoodDataProviderError as error:
        raise RuntimeError(f"USDA catalogue import failed: {error}") from error
    finally:
        await provider.aclose()
        await database.close_db()
    return imported, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-size", type=int, default=200, choices=range(1, 201))
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import every page of approved USDA datasets.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Pages to import when --all is not supplied (default: 1).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    count, skipped_count = asyncio.run(
        import_catalogue(args.page_size, None if args.all else args.max_pages)
    )
    print(
        f"Completed USDA catalogue import: {count} foods imported, {skipped_count} incomplete foods skipped."
    )
