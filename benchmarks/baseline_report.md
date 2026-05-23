# Baseline benchmark report

## Scope
Baseline instrumentation for current pipeline behavior without changing business logic or output formats.

## Telemetry format
Each LLM call now emits a single-line log entry:

`LLM_TELEMETRY step=<...> started_utc=<...> finished_utc=<...> duration_sec=<...> payload_chars=<...> response_chars=<...> parse_status=success|fail`

## Instrumented steps

| Script | Step name | Telemetry fields |
|---|---|---|
| `classify_notes.py` | `classify_note` | start/end UTC, duration, payload chars, response chars, parse status |
| `propose_clusters.py` | `propose_cluster_scheme`, `classify_note` | start/end UTC, duration, payload chars, response chars, parse status |
| `build_collection.py` | `build_collection_markdown` | start/end UTC, duration, payload chars, response chars, parse status |
| `generate_concepts.py` | `build_concept_markdown` | start/end UTC, duration, payload chars, response chars, parse status |
| `generate_index.py` | `build_index_markdown` | start/end UTC, duration, payload chars, response chars, parse status |
| `semantic_trace.py` | `stage1_rank`, `stage2_trace_notes` | start/end UTC, duration, payload chars, response chars, parse status |
| `scripts/check_contradictions.py` | `llm_assessment` | start/end UTC, duration, payload chars, response chars, parse status |

## Reproducible run commands
Use the same dataset/scope across all future optimization stages.

```bash
python classify_notes.py "<scope_folder>"
python propose_clusters.py "<scope_folder>"
python build_collection.py "<scope_folder>" primary
python build_collection.py "<scope_folder>" candidate
python generate_concepts.py primary
python generate_concepts.py candidate
python generate_index.py primary
python generate_index.py candidate
python semantic_trace.py "<query_text>"
python scripts/check_contradictions.py --help
```

## Notes
- This baseline adds only telemetry around LLM calls.
- No frontmatter conventions, naming conventions, or CLI contracts were changed.

## Automated benchmark runner

Use a single command to run all checks, collect telemetry, and produce verdict:

```bash
python scripts/run_benchmark.py --config benchmarks/benchmark_config.json --baseline benchmarks/baseline_metrics.json
```

Output artifacts are written to `benchmarks/runs/<UTC_TIMESTAMP>/`:
- `raw.log` — full stdout/stderr from executed commands
- `events.json` — parsed `LLM_TELEMETRY` events
- `metrics.json` — aggregated metrics for this run
- `compare.json` — delta vs baseline and verdict (if baseline provided)
- `summary.md` — human-readable summary table and final verdict

To create baseline metrics file initially:
1. Run without `--baseline`.
2. Copy generated `metrics.json` to `benchmarks/baseline_metrics.json`.
3. Use that baseline file in subsequent runs.
