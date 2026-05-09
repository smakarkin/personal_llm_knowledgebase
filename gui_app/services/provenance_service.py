from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from gui_app.services.frontmatter_utils import parse_frontmatter_block

WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")


@dataclass(slots=True)
class ProvenanceNode:
    kind: str
    title: str
    path: str | None = None
    children: list["ProvenanceNode"] = field(default_factory=list)


class ProvenanceService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def build_concept_lineage(self, concept_path: Path) -> ProvenanceNode:
        parsed = self._parse_note(concept_path)
        meta = parsed["meta"]
        root = ProvenanceNode("concept", concept_path.stem, str(concept_path))
        for col_link in meta.get("source_collections", []):
            col_path = self._resolve_wikilink(col_link)
            col_node = ProvenanceNode("collection", col_link, str(col_path) if col_path else None)
            if col_path and col_path.exists():
                col_parsed = self._parse_note(col_path)
                for note_link in col_parsed["meta"].get("source_notes", []):
                    note_path = self._resolve_wikilink(note_link)
                    note_node = ProvenanceNode("source_note", note_link, str(note_path) if note_path else None)
                    attachment = self._detect_attachment(note_path) if note_path else None
                    if attachment:
                        note_node.children.append(ProvenanceNode("attachment", attachment.name, str(attachment)))
                    col_node.children.append(note_node)
            root.children.append(col_node)
        return root

    def build_trace_lineage(self, trace_path: Path) -> ProvenanceNode:
        parsed = self._parse_note(trace_path)
        meta = parsed["meta"]
        root = ProvenanceNode("trace", trace_path.stem, str(trace_path))
        for link in meta.get("source_items", []):
            node = ProvenanceNode("upstream_match", link)
            note_path = self._resolve_wikilink(link)
            if note_path:
                node.path = str(note_path)
            root.children.append(node)
        for link in parsed["links"][:15]:
            root.children.append(ProvenanceNode("supporting_note", f"[[{link}]]", str(self._resolve_wikilink(link)) if self._resolve_wikilink(link) else None))
        return root

    def _parse_note(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8", errors="ignore")
        meta = {}
        body = text
        if text.startswith("---\n"):
            parts = text.split("---\n", 2)
            if len(parts) >= 3:
                meta = parse_frontmatter_block(parts[1]) or {}
                body = parts[2]
        return {"meta": meta, "body": body, "links": WIKILINK_RE.findall(body)}

    def _resolve_wikilink(self, link: str) -> Path | None:
        clean = link.strip().strip("[]")
        clean = clean.split("|")[0]
        clean = clean.replace(".md", "")
        if "/" in clean:
            p = self.repo_root / f"{clean}.md"
            return p if p.exists() else None
        hits = list(self.repo_root.glob(f"**/{clean}.md"))
        return hits[0] if hits else None

    def _detect_attachment(self, note_path: Path | None) -> Path | None:
        if note_path is None or not note_path.exists():
            return None
        text = note_path.read_text(encoding="utf-8", errors="ignore")
        for ext in ("pdf", "png", "jpg", "jpeg", "webp", "docx"):
            m = re.search(rf"\[\[([^\]]+\.{ext})\]\]", text, flags=re.IGNORECASE)
            if m:
                candidate = self.repo_root / m.group(1)
                if candidate.exists():
                    return candidate
        return None
