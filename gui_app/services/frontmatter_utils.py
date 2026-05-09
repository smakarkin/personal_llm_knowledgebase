from __future__ import annotations

from ast import literal_eval


def parse_frontmatter_block(block: str) -> dict:
    meta: dict = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if not value:
            meta[key] = ""
            continue
        low = value.lower()
        if low in {'true', 'false'}:
            meta[key] = low == 'true'
            continue
        if value.startswith('[') and value.endswith(']'):
            try:
                parsed = literal_eval(value)
                meta[key] = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                meta[key] = [value]
            continue
        meta[key] = value.strip('"\'')
    return meta


def dump_frontmatter(meta: dict) -> str:
    lines: list[str] = []
    for k, v in meta.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, list):
            rendered = ', '.join(repr(item) for item in v)
            lines.append(f"{k}: [{rendered}]")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\n"
