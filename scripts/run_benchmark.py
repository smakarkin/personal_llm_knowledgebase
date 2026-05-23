from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from statistics import mean

TELEMETRY_RE = re.compile(
    r"LLM_TELEMETRY\s+"
    r"step=(?P<step>\S+)\s+"
    r"started_utc=(?P<started>\S+)\s+"
    r"finished_utc=(?P<finished>\S+)\s+"
    r"duration_sec=(?P<duration>[0-9.]+)\s+"
    r"payload_chars=(?P<payload>\d+)\s+"
    r"response_chars=(?P<response>\d+)\s+"
    r"parse_status=(?P<parse>success|fail)"
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")


def run_commands(commands: list[str], cwd: Path, raw_log_path: Path) -> tuple[list[dict], list[dict]]:
    raw_log_path.parent.mkdir(parents=True, exist_ok=True)
    command_runs: list[dict] = []
    events: list[dict] = []

    with raw_log_path.open("w", encoding="utf-8") as raw_log:
        for idx, cmd in enumerate(commands, start=1):
            started = dt.datetime.now(dt.timezone.utc)
            raw_log.write(f"\n===== COMMAND {idx}/{len(commands)} START =====\n{cmd}\n")
            raw_log.flush()

            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                shell=True,
                text=True,
                capture_output=True,
            )

            finished = dt.datetime.now(dt.timezone.utc)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            merged_output = stdout + ("\n" if stdout and stderr else "") + stderr

            raw_log.write(merged_output)
            raw_log.write(f"\n===== COMMAND END code={proc.returncode} =====\n")
            raw_log.flush()

            for line in merged_output.splitlines():
                m = TELEMETRY_RE.search(line)
                if not m:
                    continue
                events.append(
                    {
                        "step": m.group("step"),
                        "started_utc": m.group("started"),
                        "finished_utc": m.group("finished"),
                        "duration_sec": float(m.group("duration")),
                        "payload_chars": int(m.group("payload")),
                        "response_chars": int(m.group("response")),
                        "parse_status": m.group("parse"),
                        "command": cmd,
                    }
                )

            command_runs.append(
                {
                    "command": cmd,
                    "return_code": proc.returncode,
                    "started_utc": started.isoformat(),
                    "finished_utc": finished.isoformat(),
                    "duration_sec": (finished - started).total_seconds(),
                    "stdout_chars": len(stdout),
                    "stderr_chars": len(stderr),
                }
            )

    return command_runs, events


def aggregate_metrics(command_runs: list[dict], events: list[dict]) -> dict:
    by_step: dict[str, dict] = {}

    for event in events:
        bucket = by_step.setdefault(
            event["step"],
            {
                "calls": 0,
                "duration_sec_sum": 0.0,
                "duration_sec_avg": 0.0,
                "payload_chars_sum": 0,
                "response_chars_sum": 0,
                "parse_fail_count": 0,
            },
        )
        bucket["calls"] += 1
        bucket["duration_sec_sum"] += event["duration_sec"]
        bucket["payload_chars_sum"] += event["payload_chars"]
        bucket["response_chars_sum"] += event["response_chars"]
        if event["parse_status"] != "success":
            bucket["parse_fail_count"] += 1

    for step_data in by_step.values():
        calls = step_data["calls"] or 1
        step_data["duration_sec_avg"] = step_data["duration_sec_sum"] / calls

    metrics = {
        "total_duration_sec": sum(c["duration_sec"] for c in command_runs),
        "commands_count": len(command_runs),
        "commands_failed": sum(1 for c in command_runs if c["return_code"] != 0),
        "llm_calls_count": len(events),
        "payload_chars_sum": sum(e["payload_chars"] for e in events),
        "response_chars_sum": sum(e["response_chars"] for e in events),
        "parse_fail_count": sum(1 for e in events if e["parse_status"] != "success"),
        "avg_llm_duration_sec": mean([e["duration_sec"] for e in events]) if events else 0.0,
        "by_step": by_step,
    }
    return metrics


def safe_pct_delta(new: float, old: float) -> float:
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return ((new - old) / old) * 100.0


def build_comparison(current: dict, baseline: dict, thresholds: dict) -> dict:
    comparison = {
        "payload_delta_pct": safe_pct_delta(current["payload_chars_sum"], baseline.get("payload_chars_sum", 0)),
        "response_delta_pct": safe_pct_delta(current["response_chars_sum"], baseline.get("response_chars_sum", 0)),
        "duration_delta_pct": safe_pct_delta(current["total_duration_sec"], baseline.get("total_duration_sec", 0)),
        "parse_fail_delta": current["parse_fail_count"] - baseline.get("parse_fail_count", 0),
        "commands_failed_delta": current["commands_failed"] - baseline.get("commands_failed", 0),
    }

    payload_target = -abs(float(thresholds.get("payload_improve_pct", 0)))
    duration_target = -abs(float(thresholds.get("duration_improve_pct", 0)))
    max_parse_fail_delta = int(thresholds.get("max_parse_fail_delta", 0))

    improved = (
        comparison["payload_delta_pct"] <= payload_target
        and comparison["duration_delta_pct"] <= duration_target
        and comparison["parse_fail_delta"] <= max_parse_fail_delta
        and comparison["commands_failed_delta"] <= 0
    )

    degraded = (
        comparison["parse_fail_delta"] > max_parse_fail_delta
        or comparison["commands_failed_delta"] > 0
        or (comparison["payload_delta_pct"] > 0 and comparison["duration_delta_pct"] > 0)
    )

    if improved:
        verdict = "improved"
    elif degraded:
        verdict = "degraded"
    else:
        verdict = "neutral"

    comparison["verdict"] = verdict
    comparison["thresholds"] = {
        "payload_target_pct": payload_target,
        "duration_target_pct": duration_target,
        "max_parse_fail_delta": max_parse_fail_delta,
    }
    return comparison


def write_summary_md(path: Path, metrics: dict, comparison: dict | None, baseline_path: Path | None):
    lines = [
        "# Benchmark summary",
        "",
        f"- Дата UTC: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Команд выполнено: {metrics['commands_count']}",
        f"- Команд с ошибкой: {metrics['commands_failed']}",
        f"- LLM-вызовов: {metrics['llm_calls_count']}",
        f"- Сумма payload chars: {metrics['payload_chars_sum']}",
        f"- Сумма response chars: {metrics['response_chars_sum']}",
        f"- Parse fail count: {metrics['parse_fail_count']}",
        f"- Общее время (сек): {metrics['total_duration_sec']:.3f}",
        "",
        "## По шагам",
        "",
        "| Step | Calls | Duration sum (s) | Duration avg (s) | Payload sum | Response sum | Parse fail |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for step in sorted(metrics["by_step"].keys()):
        s = metrics["by_step"][step]
        lines.append(
            f"| {step} | {s['calls']} | {s['duration_sec_sum']:.3f} | {s['duration_sec_avg']:.3f} | {s['payload_chars_sum']} | {s['response_chars_sum']} | {s['parse_fail_count']} |"
        )

    if comparison is not None and baseline_path is not None:
        lines.extend(
            [
                "",
                "## Сравнение с baseline",
                "",
                f"- Baseline: `{baseline_path.as_posix()}`",
                f"- Payload delta: {comparison['payload_delta_pct']:.2f}%",
                f"- Response delta: {comparison['response_delta_pct']:.2f}%",
                f"- Duration delta: {comparison['duration_delta_pct']:.2f}%",
                f"- Parse fail delta: {comparison['parse_fail_delta']}",
                f"- Commands failed delta: {comparison['commands_failed_delta']}",
                f"- Verdict: **{comparison['verdict']}**",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark commands, parse LLM telemetry and compare with baseline.")
    parser.add_argument("--config", required=True, help="Path to benchmark config JSON.")
    parser.add_argument("--baseline", help="Path to baseline metrics JSON.")
    parser.add_argument("--out-dir", default="benchmarks/runs", help="Directory to store benchmark runs.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve()
    out_root = (repo_root / args.out_dir).resolve()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    commands = config.get("commands", [])
    if not isinstance(commands, list) or not commands:
        raise SystemExit("Config must contain non-empty 'commands' list")

    run_dir = out_root / utc_now()
    run_dir.mkdir(parents=True, exist_ok=True)

    command_runs, events = run_commands(commands, repo_root, run_dir / "raw.log")
    metrics = aggregate_metrics(command_runs, events)

    (run_dir / "command_runs.json").write_text(json.dumps(command_runs, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison = None
    baseline_path = None
    if args.baseline:
        baseline_path = (repo_root / args.baseline).resolve()
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        thresholds = config.get("thresholds", {}) if isinstance(config.get("thresholds", {}), dict) else {}
        comparison = build_comparison(metrics, baseline, thresholds)
        (run_dir / "compare.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    write_summary_md(run_dir / "summary.md", metrics, comparison, baseline_path)

    print(f"RUN_DIR={run_dir}")
    if comparison:
        print(f"VERDICT={comparison['verdict']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
