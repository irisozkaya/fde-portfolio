"""Persistent API spend ledger. The engagement's total API budget is capped at $5."""
import json
from datetime import datetime, timezone
from pathlib import Path

BUDGET_CAP_USD = 5.00


class BudgetExceeded(RuntimeError):
    pass


class SpendLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"entries": []}
        return json.loads(self.path.read_text())

    def add(self, cost_usd: float, source: str) -> None:
        data = self._load()
        data["entries"].append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "source": source, "cost_usd": cost_usd})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1))

    def total(self) -> float:
        return sum(e["cost_usd"] for e in self._load()["entries"])

    def is_over_cap(self, cap: float = BUDGET_CAP_USD) -> bool:
        return self.total() >= cap
