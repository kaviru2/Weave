#!/usr/bin/env python3
"""Gemini zero-shot point-prediction eval on the GoKer held-out test set.

Runs models sequentially with live Rich progress display.
Exponential backoff on rate limits.

Usage:
    uv run python eval/gemini_zeroshot_goker.py
    uv run python eval/gemini_zeroshot_goker.py --models gemini-3.5-flash
    uv run python eval/gemini_zeroshot_goker.py --models gemini-3.5-flash gemini-3.1-pro-preview
    uv run python eval/gemini_zeroshot_goker.py --sample 50 --no-thinking
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

load_dotenv()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL_FILE = os.path.join(REPO_ROOT, "dataset", "output", "kaggle_upload", "val_point_dups.jsonl")
RESULTS_DIR = os.path.join(REPO_ROOT, "eval", "results")

BACKOFF_BASE = 5
BACKOFF_MAX = 120

console = Console()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def call_gemini(
    client: genai.Client,
    model: str,
    system: str,
    prompt: str,
    thinking_budget: int,
) -> str:
    config_kwargs: dict = {
        "system_instruction": system,
        "temperature": 0.0,
        "max_output_tokens": 4096 if thinking_budget != 0 else 256,
    }
    if thinking_budget != 0:
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_budget=thinking_budget
        )
    config = genai_types.GenerateContentConfig(**config_kwargs)

    wait = BACKOFF_BASE
    for attempt in range(6):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
            return resp.text or ""
        except Exception as exc:
            msg = str(exc)
            retryable = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower() or "500" in msg or "503" in msg
            if retryable and attempt < 5:
                time.sleep(wait)
                wait = min(wait * 2, BACKOFF_MAX)
                continue
            raise RuntimeError(f"API error: {msg[:120]}") from exc
    return ""


def parse_event_type(raw: str) -> Optional[str]:
    text = raw.strip()
    if text.startswith("```"):
        _, _, rest = text.partition("\n")
        text = rest.rstrip("`").strip()
    try:
        return json.loads(text).get("event_type")
    except Exception:
        pass
    for start in range(len(text)):
        if text[start] == "{":
            for end in range(len(text), start, -1):
                try:
                    return json.loads(text[start:end]).get("event_type")
                except Exception:
                    continue
    return None


# ---------------------------------------------------------------------------
# Rich layout builders
# ---------------------------------------------------------------------------

def make_layout(
    model: str,
    thinking_label: str,
    progress: Progress,
    correct: int,
    total_done: int,
    total: int,
    errors: int,
    last_gt: str,
    last_pred: str,
    last_match: Optional[bool],
    per_pattern: dict,
    per_nd: dict,
) -> Table:
    acc = correct / total_done if total_done else 0.0

    # ── header ──────────────────────────────────────────────
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold cyan")
    header.add_column()
    header.add_row("Model:", model)
    header.add_row("Thinking:", thinking_label)

    # ── live stats ──────────────────────────────────────────
    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column(style="dim")
    stats.add_column(justify="right")

    color = "green" if acc >= 0.4 else "yellow" if acc >= 0.2 else "red"
    stats.add_row("Accuracy", f"[bold {color}]{correct}/{total_done} = {acc:.1%}[/]")
    stats.add_row("Errors", f"[red]{errors}[/]" if errors else "0")

    if last_match is not None:
        sym = "[green]✓[/]" if last_match else "[red]✗[/]"
        gt_s = f"[dim]{last_gt or '?'}[/]"
        pred_color = "green" if last_match else "red"
        pred_s = f"[{pred_color}]{last_pred or '?'}[/]"
        stats.add_row("Last gt", gt_s)
        stats.add_row("Last pred", pred_s + f"  {sym}")

    # ── breakdown by pattern ────────────────────────────────
    pat_table = Table(title="By pattern", show_header=True, box=None, padding=(0, 1))
    pat_table.add_column("Pattern", style="dim", min_width=12)
    pat_table.add_column("Acc", justify="right")
    pat_table.add_column("n", justify="right", style="dim")
    for p, c in sorted(per_pattern.items()):
        a = c["correct"] / c["total"] if c["total"] else 0
        col = "green" if a >= 0.4 else "yellow" if a >= 0.2 else "red"
        pat_table.add_row(p, f"[{col}]{a:.0%}[/]", str(c["total"]))

    # ── breakdown by nondeterminism ─────────────────────────
    nd_table = Table(title="By nondeterminism", show_header=True, box=None, padding=(0, 1))
    nd_table.add_column("Level", style="dim", min_width=8)
    nd_table.add_column("Acc", justify="right")
    nd_table.add_column("n", justify="right", style="dim")
    for n, c in sorted(per_nd.items()):
        a = c["correct"] / c["total"] if c["total"] else 0
        col = "green" if a >= 0.4 else "yellow" if a >= 0.2 else "red"
        nd_table.add_row(n, f"[{col}]{a:.0%}[/]", str(c["total"]))

    root = Table.grid(padding=1)
    root.add_row(Panel(header, title="[bold]Weave GoKer Eval", border_style="cyan"))
    root.add_row(Panel(stats, title="Live stats", border_style="blue"))
    root.add_row(progress)
    root.add_row(Columns([pat_table, nd_table], equal=True, expand=True))
    return root


# ---------------------------------------------------------------------------
# Main eval loop
# ---------------------------------------------------------------------------

def run_model(
    client: genai.Client,
    model: str,
    examples: list[dict],
    thinking_budget: int,
) -> dict:
    total = len(examples)
    correct = 0
    errors = 0
    per_pattern: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    per_nd: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    per_example = []

    thinking_label = (
        "auto (model decides)" if thinking_budget == -1
        else "disabled" if thinking_budget == 0
        else f"{thinking_budget} tokens"
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
    task_id = progress.add_task(f"[cyan]{model}", total=total)

    last_gt: str = ""
    last_pred: str = ""
    last_match: Optional[bool] = None
    t0 = time.time()

    with Live(
        make_layout(model, thinking_label, progress, 0, 0, total, 0, "", "", None, per_pattern, per_nd),
        console=console,
        refresh_per_second=4,
    ) as live:
        for i, ex in enumerate(examples):
            messages = ex["messages"]
            pattern = ex.get("concurrency_pattern", "unknown")
            nd = ex.get("nondeterminism", "unknown")

            system_content = next(
                (m["content"] for m in messages if m["role"] == "system"),
                "You are a code execution simulator.",
            )
            user_content = next(
                (m["content"] for m in messages if m["role"] == "user"), ""
            )
            gt_raw = next(
                (m["content"] for m in messages if m["role"] == "assistant"), ""
            )
            try:
                gt_event_type = json.loads(gt_raw).get("event_type")
            except Exception:
                gt_event_type = None

            raw = ""
            pred_event_type = None
            error_msg = None
            try:
                raw = call_gemini(
                    client, model, system_content, user_content, thinking_budget
                )
                pred_event_type = parse_event_type(raw)
            except Exception as exc:
                error_msg = str(exc)[:160]
                errors += 1

            match = bool(gt_event_type and pred_event_type and gt_event_type == pred_event_type)
            if match:
                correct += 1

            per_pattern[pattern]["total"] += 1
            per_nd[nd]["total"] += 1
            if match:
                per_pattern[pattern]["correct"] += 1
                per_nd[nd]["correct"] += 1

            per_example.append({
                "index": i,
                "ground_truth_event_type": gt_event_type,
                "predicted_event_type": pred_event_type,
                "match": match,
                "pattern": pattern,
                "nondeterminism": nd,
                "error": error_msg,
            })

            last_gt = gt_event_type or "?"
            last_pred = pred_event_type or ("ERROR" if error_msg else "?")
            last_match = match if error_msg is None else False

            progress.advance(task_id)
            live.update(
                make_layout(
                    model, thinking_label, progress,
                    correct, i + 1, total, errors,
                    last_gt, last_pred, last_match,
                    per_pattern, per_nd,
                )
            )

    elapsed = time.time() - t0
    accuracy = correct / total if total else 0.0

    return {
        "model": model,
        "thinking_budget": thinking_budget,
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "errors": errors,
        "elapsed_seconds": elapsed,
        "by_pattern": {k: v for k, v in per_pattern.items()},
        "by_nondeterminism": {k: v for k, v in per_nd.items()},
        "per_example": per_example,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gemini zero-shot eval on GoKer held-out test set"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemini-3.5-flash", "gemini-3.1-pro-preview"],
    )
    parser.add_argument(
        "--thinking-budget", type=int, default=-1, metavar="N",
        help="-1=auto (default), 0=disabled, N=fixed token budget",
    )
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--sample", type=int, default=None, metavar="N")
    parser.add_argument("--val-file", default=VAL_FILE)
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        console.print("[bold red]ERROR:[/] GEMINI_API_KEY not set in .env")
        sys.exit(1)

    thinking_budget = 0 if args.no_thinking else args.thinking_budget

    with open(args.val_file) as f:
        examples = [json.loads(line) for line in f]

    if args.sample:
        random.seed(42)
        examples = random.sample(examples, min(args.sample, len(examples)))
        console.print(f"[dim]Sampled {len(examples)} examples (seed=42)[/]")

    console.print(f"[bold]GoKer val set:[/] {len(examples)} examples")
    console.print(f"[bold]Models:[/] {' → '.join(args.models)}")

    client = genai.Client(api_key=api_key)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    all_results = []
    for model in args.models:
        result = run_model(client, model, examples, thinking_budget)
        all_results.append(result)

        slug = model.replace("/", "-").replace(".", "_")
        thinking_label = f"_thinking{thinking_budget}" if thinking_budget != 0 else ""
        sample_label = f"_n{args.sample}" if args.sample else ""
        out_path = os.path.join(
            RESULTS_DIR, f"gemini_goker_{slug}{thinking_label}{sample_label}.json"
        )
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"[green]Saved:[/] {out_path}")

    # ── final comparison table ───────────────────────────────
    table = Table(title="GoKer Zero-Shot Final Results", show_lines=True)
    table.add_column("Model", style="cyan")
    table.add_column("Accuracy", justify="right")
    table.add_column("Correct", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Notes")

    for r in all_results:
        acc = r["accuracy"]
        col = "green" if acc >= 0.4 else "yellow" if acc >= 0.2 else "red"
        table.add_row(
            r["model"],
            f"[{col}]{acc:.1%}[/]",
            f"{r['correct']}/{r['total']}",
            str(r["errors"]),
            "thinking=auto" if thinking_budget == -1 else "no thinking",
        )

    table.add_section()
    table.add_row(
        "Qwen 7B fine-tuned (Phase 13)", "[green]36.2%[/]", "289/798", "0",
        "GoKer OOD — QLoRA Unsloth"
    )
    table.add_row(
        "Qwen 1.5B fine-tuned (Phase 12)", "[yellow]40.2%[/]", "—", "0",
        "in-distribution only"
    )
    table.add_row(
        "Gemini zero-shot (Phase 4)", "[green]56.0%[/]", "—", "0",
        "in-distribution only"
    )
    console.print(table)

    summary_path = os.path.join(RESULTS_DIR, "gemini_goker_summary.json")
    with open(summary_path, "w") as f:
        json.dump(
            {
                "models": all_results,
                "finetuned_7b_goker": 0.362,
                "finetuned_1.5b_indist": 0.402,
                "gemini_indist_phase4": 0.560,
            },
            f,
            indent=2,
        )
    console.print(f"[dim]Summary: {summary_path}[/]")


if __name__ == "__main__":
    main()
