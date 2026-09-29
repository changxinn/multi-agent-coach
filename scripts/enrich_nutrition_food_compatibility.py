"""Create conservative, auditable food-compatibility review queue entries."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Permit direct invocation from the repository root on Windows and Unix shells.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from services.nutrition_agent.app.config import Settings
from services.nutrition_agent.app.food_compatibility_enrichment import (
    CompatibilityCandidate,
    classify_food_for_review,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="usda")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--resume-after-id", type=int, default=0)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="write preliminary review entries"
    )
    parser.add_argument(
        "--force", action="store_true", help="re-triage unchanged non-approved rows"
    )
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.resume_after_id < 0:
        parser.error("--resume-after-id cannot be negative")
    return args


async def fetch_foods(connection, args: argparse.Namespace) -> list[dict[str, Any]]:
    result = await connection.execute(
        text(
            """
            SELECT food.id, food.provider, food.provider_food_id, food.description,
                   food.raw_response, compatibility.input_fingerprint,
                   compatibility.review_status
            FROM nutrition_food_cache AS food
            LEFT JOIN nutrition_food_compatibility AS compatibility
              ON compatibility.food_cache_id = food.id
            WHERE food.provider = :provider
              AND food.id > :resume_after_id
              AND COALESCE(compatibility.review_status, 'pending') <> 'approved'
            ORDER BY food.id
            LIMIT :batch_size
            """
        ),
        {
            "provider": args.provider,
            "resume_after_id": args.resume_after_id,
            "batch_size": args.batch_size,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def upsert_candidate(connection, candidate: CompatibilityCandidate) -> bool:
    """Upsert preliminary metadata, never replacing an approved human decision."""
    result = await connection.execute(
        text(
            """
            INSERT INTO nutrition_food_compatibility (
                food_cache_id, review_status, allergen_status, known_allergens,
                strict_suitability, evidence, confidence, classifier_version,
                policy_version, input_fingerprint, updated_at
            ) VALUES (
                :food_cache_id, :review_status, :allergen_status,
                CAST(:known_allergens AS jsonb), CAST(:strict_suitability AS jsonb),
                CAST(:evidence AS jsonb), :confidence, :classifier_version,
                :policy_version, :input_fingerprint, CURRENT_TIMESTAMP
            )
            ON CONFLICT (food_cache_id) DO UPDATE SET
                review_status = EXCLUDED.review_status,
                allergen_status = EXCLUDED.allergen_status,
                known_allergens = EXCLUDED.known_allergens,
                strict_suitability = EXCLUDED.strict_suitability,
                evidence = EXCLUDED.evidence,
                confidence = EXCLUDED.confidence,
                classifier_version = EXCLUDED.classifier_version,
                policy_version = EXCLUDED.policy_version,
                input_fingerprint = EXCLUDED.input_fingerprint,
                updated_at = CURRENT_TIMESTAMP
            WHERE nutrition_food_compatibility.review_status <> 'approved'
            """
        ),
        {
            **candidate.asdict(),
            "known_allergens": json.dumps(candidate.known_allergens),
            "strict_suitability": json.dumps(candidate.strict_suitability),
            "evidence": json.dumps(candidate.evidence),
        },
    )
    return result.rowcount > 0


async def enrich(args: argparse.Namespace, connection) -> dict[str, Any]:
    """Process one stable batch and return a serializable audit report."""
    report: dict[str, Any] = {
        "apply": args.apply,
        "provider": args.provider,
        "resume_after_id": args.resume_after_id,
        "records": [],
        "summary": {"considered": 0, "written": 0, "skipped_unchanged": 0},
    }
    for food in await fetch_foods(connection, args):
        candidate = classify_food_for_review(food)
        report["summary"]["considered"] += 1
        record: dict[str, Any] = {
            "food_cache_id": candidate.food_cache_id,
            "description": food["description"],
            "candidate": candidate.asdict(),
        }
        if (
            not args.force
            and food.get("input_fingerprint") == candidate.input_fingerprint
        ):
            record["outcome"] = "skipped_unchanged"
            report["summary"]["skipped_unchanged"] += 1
        elif args.apply:
            record["outcome"] = (
                "written"
                if await upsert_candidate(connection, candidate)
                else "protected_approved"
            )
            if record["outcome"] == "written":
                report["summary"]["written"] += 1
        else:
            record["outcome"] = "dry_run"
        report["records"].append(record)
    return report


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    settings = Settings()
    if not settings.DATABASE_URL:
        raise RuntimeError(
            "NUTRITION_DATABASE_URL is required for compatibility enrichment"
        )
    database_url = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            return await enrich(args, connection)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = asyncio.run(main_async(args))
    encoded_report = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.report:
        args.report.write_text(encoded_report + "\n", encoding="utf-8")
    print(encoded_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
