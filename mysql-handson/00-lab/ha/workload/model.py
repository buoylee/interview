from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Iterable


class Outcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OrderRequest:
    request_id: str
    payload: str
    router: str


@dataclass(frozen=True)
class LedgerRecord:
    request_id: str
    payload: str
    router: str
    started_at: str
    finished_at: str
    outcome: Outcome
    retries: int
    error_type: str | None

    def to_json(self) -> str:
        value = asdict(self)
        value["outcome"] = self.outcome.value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "LedgerRecord":
        data = json.loads(value)
        data["outcome"] = Outcome(data["outcome"])
        return cls(**data)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class JsonlLedger:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: LedgerRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.to_json() + "\n")
            handle.flush()

    @staticmethod
    def load(paths: Iterable[Path]) -> list[LedgerRecord]:
        records: list[LedgerRecord] = []
        for path in sorted(paths):
            if path.exists():
                records.extend(
                    LedgerRecord.from_json(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
        return records
