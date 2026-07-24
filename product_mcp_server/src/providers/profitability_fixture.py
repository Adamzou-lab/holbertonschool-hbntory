"""Implementation fixture du ProfitabilityDataProvider.

Genere des evenements synthetiques deterministes a partir d'un seed.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ..schemas.margin import ProfitabilityData, PurchaseEvent, SaleEvent

FIXTURE_VERSION = "fixture_v1"


class FixtureProfitabilityProvider:
    """Genere des ventes et achats synthetiques (Decimal, deterministe)."""

    async def get_events(
        self,
        *,
        days: int,
        seed: int | None = None,
    ) -> ProfitabilityData:
        days = max(7, min(days, 730))
        seed = seed if seed is not None else 42
        rng = random.Random(seed)
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=days)

        products = list(range(1, 41))
        branches = [1, 2]
        suppliers = ["SUP-HBT-001", "SUP-LAB-002", "SUP-CMP-003", "SUP-WEB-004", "SUP-OPS-005"]

        sales: list[SaleEvent] = []
        for _ in range(days * 3):
            pid = rng.choice(products)
            bid = rng.choice(branches)
            qty = rng.randint(1, 10)
            unit = Decimal(str(round(rng.uniform(10.0, 500.0), 2)))
            ts = cutoff + timedelta(days=rng.uniform(0, days), seconds=rng.uniform(0, 86400))
            sales.append(
                SaleEvent(
                    product_id=pid,
                    branch_id=bid,
                    quantity=qty,
                    unit_sale_amount=unit,
                    currency="USD",
                    occurred_at=ts,
                )
            )

        purchases: list[PurchaseEvent] = []
        for _ in range(max(20, days // 2)):
            pid = rng.choice(products)
            sid = rng.choice(suppliers)
            qty = rng.randint(10, 100)
            unit_cost = Decimal(str(round(rng.uniform(5.0, 400.0), 2)))
            freight = Decimal(str(round(rng.uniform(0.0, 50.0), 2)))
            ts = cutoff + timedelta(days=rng.uniform(0, days), seconds=rng.uniform(0, 86400))
            purchases.append(
                PurchaseEvent(
                    product_id=pid,
                    supplier_id=sid,
                    quantity=qty,
                    unit_purchase_cost=unit_cost,
                    freight_cost=freight,
                    currency="USD",
                    occurred_at=ts,
                )
            )

        return ProfitabilityData(
            sales=sales,
            purchases=purchases,
            generated_at=now,
            seed=seed,
        )


__all__ = ["FixtureProfitabilityProvider", "FIXTURE_VERSION"]
