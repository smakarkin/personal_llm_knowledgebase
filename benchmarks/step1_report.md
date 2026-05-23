# Step1 benchmark report (prompt/payload compression)

## Commands (same as baseline)
- `python classify_notes.py "<scope_folder>"`
- `python propose_clusters.py "<scope_folder>"`
- `python build_collection.py "<scope_folder>" primary`
- `python build_collection.py "<scope_folder>" candidate`
- `python generate_concepts.py primary`
- `python generate_concepts.py candidate`
- `python generate_index.py primary`
- `python generate_index.py candidate`
- `python semantic_trace.py "<query_text>"`
- `python scripts/check_contradictions.py --help`

## Before/After summary

| Metric | Before (baseline) | After (step1 run) |
|---|---:|---:|
| chars in (payload) | N/A in baseline file (telemetry format only) | N/A (runtime blocked before LLM calls due missing dependency) |
| chars out (response) | N/A in baseline file (telemetry format only) | N/A (runtime blocked before LLM calls due missing dependency) |
| runtime | N/A in baseline file | N/A for 9/10 commands (blocked), `--help` succeeded |
| parse errors | N/A in baseline file | N/A (no LLM parse stage reached) |

## Execution notes
- Environment missing `PyYAML` (`ModuleNotFoundError: No module named 'yaml'`) for all pipeline scripts importing `yaml`.
- `python scripts/check_contradictions.py --help` completed successfully.
