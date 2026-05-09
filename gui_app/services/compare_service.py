from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class CompareResult:
    left: str
    right: str
    shared_sources: list[str]
    differing_claims: list[str]
    recommendation: str


class CompareService:
    def compare_notes(self, left_path: Path, right_path: Path) -> CompareResult:
        left = left_path.read_text(encoding="utf-8", errors="ignore")
        right = right_path.read_text(encoding="utf-8", errors="ignore")
        left_links = set(re.findall(r"\[\[(.+?)\]\]", left))
        right_links = set(re.findall(r"\[\[(.+?)\]\]", right))
        shared = sorted(left_links & right_links)
        left_b = [x.strip("- ") for x in left.splitlines() if x.startswith("-")]
        right_b = [x.strip("- ") for x in right.splitlines() if x.startswith("-")]
        diff = sorted(set(left_b).symmetric_difference(set(right_b)))[:15]
        if len(shared) >= 3 and len(diff) <= 5:
            rec = "Рекомендация: merge (много общих источников и близкие claims)."
        elif len(shared) == 0 and len(diff) >= 5:
            rec = "Рекомендация: keep separate (разные источники/claims)."
        else:
            rec = "Рекомендация: split/уточнить framing через manual review."
        return CompareResult(left=left_path.name, right=right_path.name, shared_sources=shared, differing_claims=diff, recommendation=rec)
