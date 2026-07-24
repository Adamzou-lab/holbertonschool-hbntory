"""Generateur de fixture de profitabilite (deterministe).

Usage :
    python -m scripts.generate_profitability_fixture --seed 42 --days 180 --sales 1000 --purchases 200

Le resultat est ecrit en JSON sur stdout ou dans --output <path>.
"""

from __future__ import annotations

import argparse
import json
import sys

from ..providers.profitability_fixture import FixtureProfitabilityProvider
from ..schemas.margin import ProfitabilityData


async def _main_async(args: argparse.Namespace) -> None:
    provider = FixtureProfitabilityProvider()
    data: ProfitabilityData = await provider.get_events(
        days=args.days, seed=args.seed
    )
    payload = data.model_dump(mode="json")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote {args.output}")
    else:
        json.dump(payload, sys.stdout, indent=2)
        print()


def main() -> None:
    p = argparse.ArgumentParser(description="Generateur de fixture profitabilite")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--sales", type=int, default=1000, help="Indicatif uniquement ; le generateur produit ~3*days.")
    p.add_argument("--purchases", type=int, default=200)
    p.add_argument("--output", type=str, default=None)
    args = p.parse_args()
    import asyncio

    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
