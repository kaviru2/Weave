#!/usr/bin/env python3
"""Rich dashboard for all active Weave eval pods. Usage: python scripts/monitor_pods.py [--once]"""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    from rich.layout import Layout
    from rich import box
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "rich", "-q", "--break-system-packages"],
        check=True
    )
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    from rich.layout import Layout
    from rich import box

PODS = [
    {
        "name": "Phase 24",
        "desc": "7B Wrapper / Qwen2.5-Coder / RTX 4000 Ada",
        "host": os.environ.get("RUNPOD_IP", "213.173.108.13"),
        "port": os.environ.get("RUNPOD_PORT", "18549"),
        "log":  "/root/train.log",
        "result": "/root/lora_adapter_traj/adapter_config.json",
        "color": "magenta",
    },
]

KEY = os.path.expanduser("~/.ssh/id_runpod")
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes"]
REFRESH = 30


def ssh(host, port, cmd):
    try:
        r = subprocess.run(
            ["ssh"] + SSH_OPTS + ["-p", port, "-i", KEY, f"root@{host}", cmd],
            capture_output=True, text=True, timeout=12,
        )
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return f"(error: {e})"


def fetch_pod(pod):
    host, port = pod["host"], pod["port"]
    done_raw   = ssh(host, port, f"test -f {pod['result']} && echo DONE || echo RUNNING")
    # Extract last tqdm step line + last few INFO lines separately
    log_raw    = ssh(host, port,
        f"{{ grep -oE '[0-9]+%\\|[^|]*\\| [0-9]+/[0-9]+ \\[[^]]+\\]' {pod['log']} 2>/dev/null | tail -1; "
        f"grep -E 'INFO|accuracy|Accuracy|loss|Error|Traceback|Training completed|PHASE' {pod['log']} 2>/dev/null | tail -5; }} || "
        f"tail -6 {pod['log']} 2>/dev/null || echo '(log not yet created)'")
    gpu_raw    = ssh(host, port,
        "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu "
        "--format=csv,noheader,nounits 2>/dev/null || echo 'N/A'")
    disk_raw   = ssh(host, port, "df -h /workspace 2>/dev/null | tail -1")
    return {**pod, "done": done_raw == "DONE", "log": log_raw, "gpu": gpu_raw, "disk": disk_raw}


def parse_gpu(raw):
    if raw == "N/A" or not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 5:
        return None
    return {"name": parts[0], "util": parts[1], "mem_used": parts[2], "mem_total": parts[3], "temp": parts[4]}


def make_table(results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    table = Table(
        title=f"[bold white]WEAVE EVAL MONITOR[/]  [dim]{now}[/]  [dim]Ctrl+C to stop[/]",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
        title_justify="left",
        header_style="bold white on #1c1c1c",
    )
    table.add_column("Pod", style="bold", width=10, no_wrap=True)
    table.add_column("Status", width=8, justify="center")
    table.add_column("GPU  util / mem / temp", width=28)
    table.add_column("Network Vol", width=14)
    table.add_column("Recent log", min_width=40)

    for r in results:
        color = r["color"]

        # Status
        if "(error" in r["log"] or "(unreachable)" in r["log"]:
            status = Text("UNREACHABLE", style="bold red")
        elif r["done"]:
            status = Text("DONE ✓", style="bold green")
        else:
            status = Text("RUNNING", style=f"bold {color}")

        # GPU
        g = parse_gpu(r["gpu"])
        if g:
            util_val = int(g["util"]) if g["util"].isdigit() else 0
            util_bar = "█" * (util_val // 10) + "░" * (10 - util_val // 10)
            util_color = "green" if util_val > 50 else ("yellow" if util_val > 10 else "red")
            gpu_text = Text()
            gpu_text.append(f"{util_val:3d}%  ", style=util_color)
            gpu_text.append(util_bar, style=f"dim {util_color}")
            gpu_text.append(f"\n{g['mem_used']}MB / {g['mem_total']}MB  {g['temp']}°C", style="dim")
        else:
            gpu_text = Text("N/A", style="dim red")

        # Disk
        disk_parts = r["disk"].split() if r["disk"] else []
        if len(disk_parts) >= 5:
            disk_text = Text()
            disk_text.append(f"{disk_parts[2]} used\n", style="white")
            pct = disk_parts[4]
            pct_int = int(pct.rstrip("%")) if pct.rstrip("%").isdigit() else 0
            disk_color = "red" if pct_int >= 90 else ("yellow" if pct_int >= 75 else "green")
            disk_text.append(pct, style=f"bold {disk_color}")
            disk_text.append(f" of {disk_parts[1]}", style="dim")
        else:
            disk_text = Text("—", style="dim")

        # Log
        lines = r["log"].splitlines()[-6:]
        log_text = Text()
        for line in lines:
            if "Error" in line or "error" in line or "Traceback" in line:
                log_text.append(line + "\n", style="red")
            elif "%" in line and "/" in line:
                log_text.append(line + "\n", style=color)
            elif "DONE" in line or "✓" in line or "Accuracy" in line.title():
                log_text.append(line + "\n", style="bold green")
            else:
                log_text.append(line + "\n", style="dim white")

        pod_label = Text()
        pod_label.append(r["name"] + "\n", style=f"bold {color}")
        pod_label.append(r["desc"], style="dim")

        table.add_row(pod_label, status, gpu_text, disk_text, log_text)

    return table


def fetch_all():
    results = [None] * len(PODS)
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fetch_pod, pod): i for i, pod in enumerate(PODS)}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()
    return results


def main():
    once = "--once" in sys.argv
    console = Console()

    if once:
        results = fetch_all()
        console.print(make_table(results))
        return

    with Live(console=console, refresh_per_second=1, screen=False) as live:
        while True:
            results = fetch_all()
            live.update(make_table(results))
            for _ in range(REFRESH * 2):
                time.sleep(0.5)
                # rerender countdown in title without refetching
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                live.update(make_table(results))  # keeps display alive


if __name__ == "__main__":
    main()
