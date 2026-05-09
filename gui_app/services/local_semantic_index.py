from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import re
from collections import Counter, defaultdict

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{2,}")


@dataclass(frozen=True)
class SearchHit:
    path: Path
    layer: str
    score: float
    title: str
    preview: str
    meta: dict


class LocalSemanticIndex:
    """Локальный индекс markdown-слоёв (без внешнего сервера/БД)."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.index_file = repo_root / "gui_app" / "gui_app_data" / "semantic_index.json"
        self._data: dict = {"docs": [], "idf": {}, "updated_at": ""}

    def rebuild(self, include_traces: bool = False) -> dict:
        docs = []
        for layer, folder in [
            ("collection", "11_llm_collections_primary"),
            ("collection", "11_llm_collections_candidate"),
            ("concept", "12_llm_concepts"),
            ("index", "13_llm_indexes"),
            ("trace", "14_llm_traces"),
        ]:
            if layer == "trace" and not include_traces:
                continue
            root = self.repo_root / folder
            if not root.exists():
                continue
            for p in root.glob("*.md"):
                text = p.read_text(encoding="utf-8", errors="ignore")
                title = p.stem
                meta = self._parse_frontmatter(text)
                body = self._body(text)
                tokens = self._tokens(f"{title} {body}")
                docs.append({
                    "path": str(p.relative_to(self.repo_root)),
                    "layer": layer,
                    "title": title,
                    "meta": meta,
                    "preview": body[:240],
                    "tf": Counter(tokens),
                    "len": max(len(tokens), 1),
                })
        idf = self._build_idf(docs)
        for d in docs:
            d["tf"] = dict(d["tf"])
        self._data = {"docs": docs, "idf": idf, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.index_file.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"documents": len(docs), "updated_at": self._data["updated_at"]}

    def load(self) -> None:
        if self.index_file.exists():
            self._data = json.loads(self.index_file.read_text(encoding="utf-8"))

    def search(self, query: str, *, layer: str | None = None, mode: str | None = None, cluster: str | None = None, limit: int = 30) -> list[SearchHit]:
        self.load()
        q_tokens = self._tokens(query)
        if not q_tokens:
            return []
        q_tf = Counter(q_tokens)
        q_norm = math.sqrt(sum((q_tf[t] * self._data["idf"].get(t, 0.0)) ** 2 for t in q_tf)) or 1.0
        hits: list[SearchHit] = []
        for d in self._data.get("docs", []):
            if layer and d["layer"] != layer:
                continue
            if mode and str(d["meta"].get("collection_mode") or d["meta"].get("concept_mode") or d["meta"].get("index_mode") or "") != mode:
                continue
            if cluster and cluster.lower() not in str(d["meta"].get("cluster", "")).lower():
                continue
            score = self._cosine(q_tf, q_norm, d)
            if score <= 0:
                continue
            hits.append(SearchHit(path=self.repo_root / d["path"], layer=d["layer"], score=score, title=d["title"], preview=d["preview"], meta=d["meta"]))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:limit]

    def _cosine(self, q_tf: Counter, q_norm: float, doc: dict) -> float:
        dot = 0.0
        d_norm_sq = 0.0
        for term, tf in doc["tf"].items():
            w = (tf / doc["len"]) * self._data["idf"].get(term, 0.0)
            d_norm_sq += w * w
        d_norm = math.sqrt(d_norm_sq) or 1.0
        for term, tf in q_tf.items():
            dot += (tf * self._data["idf"].get(term, 0.0)) * ((doc["tf"].get(term, 0) / doc["len"]) * self._data["idf"].get(term, 0.0))
        return dot / (q_norm * d_norm)

    def _build_idf(self, docs: list[dict]) -> dict[str, float]:
        df = defaultdict(int)
        for d in docs:
            for t in d["tf"].keys():
                df[t] += 1
        n = max(len(docs), 1)
        return {t: math.log((1 + n) / (1 + v)) + 1.0 for t, v in df.items()}

    def _parse_frontmatter(self, text: str) -> dict:
        if not text.startswith("---\n"):
            return {}
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            return {}
        meta = {}
        for line in parts[1].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
        return meta

    def _body(self, text: str) -> str:
        if text.startswith("---\n"):
            parts = text.split("---\n", 2)
            if len(parts) >= 3:
                return parts[2]
        return text

    def _tokens(self, text: str) -> list[str]:
        return [t.lower() for t in TOKEN_RE.findall(text)]
