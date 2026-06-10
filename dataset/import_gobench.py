#!/usr/bin/env python3
"""
dataset/import_gobench.py

Recursively scans the GoBench (GoKer) directory, extracts the simplified
human-written concurrency bug kernels, instruments them with Weave trace
headers and package main wrappers, verifies compilation safety, and saves
them to programs/ as goker_<project>_<bug_id>.go.

Run:
  .venv/bin/python dataset/import_gobench.py
"""

import os
import re
import sys
import glob
import shutil
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOBENCH_GOKER_DIR = os.path.join(BASE_DIR, "gobench_temp", "gobench", "goker")
PROGRAMS_DIR = os.path.join(BASE_DIR, "programs")


def inject_trace_header() -> str:
    """Returns the standard trace startup header used in all Weave programs."""
    return """\tif tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
\t\tf, err := os.Create(tf)
\t\tif err == nil {
\t\t\tif err := trace.Start(f); err == nil {
\t\t\t\tdefer func() { trace.Stop(); f.Close() }()
\t\t\t}
\t\t}
\t}"""


def verify_compilation(file_path: str) -> bool:
    """Verifies that the generated Go file compiles cleanly using go build."""
    try:
        go_bin = "go"
        for path in ["/opt/homebrew/bin/go", "/usr/local/bin/go"]:
            if os.path.exists(path):
                go_bin = path
                break

        res = subprocess.run(
            [go_bin, "build", "-o", os.devnull, file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return res.returncode == 0
    except Exception as e:
        logging.error(f"Error executing go build: {e}")
        return False


def instrument_goker_file(
    src_path: str,
    project: str,
    bug_id: str,
    outcome: str
) -> Optional[str]:
    """
    Parses a GoBench test file and converts it into a standalone executable package main
    with Weave trace instrumentation.
    """
    with open(src_path, "r") as f:
        content = f.read()

    # 1. Skip files that import external packages (to keep them self-contained)
    # We only allow standard library imports. If we see non-standard imports, skip.
    # Standard library imports don't have periods in their paths (except golang.org/x).
    non_std_imports = re.findall(r'"([^"]+\.[^"]+)"', content)
    if non_std_imports:
        # Check if they are just standard testing/golang packages
        for imp in non_std_imports:
            if not imp.startswith("golang.org/x/"):
                logging.debug(f"Skipping {src_path} due to non-std import: {imp}")
                return None

    # 2. Change package to main
    content = re.sub(r"package\s+[a-zA-Z0-9_]+", "package main", content, count=1)

    # 3. Add os and runtime/trace to imports, remove testing
    # Look for import block
    if "import (" in content:
        # Add "os", "runtime/trace" to import block
        content = content.replace('import (', 'import (\n\t"os"\n\t"runtime/trace"', 1)
        # Remove testing import
        content = re.sub(r'"testing"\n?', "", content)
    else:
        # No import block, single line import or none
        content = content.replace("import ", 'import (\n\t"os"\n\t"runtime/trace"\n)\nimport ', 1)
        content = re.sub(r'import\s+"testing"\n?', "", content)

    # 4. Convert Test function to main()
    # Find func TestFoo(t *testing.T) {
    test_func_match = re.search(r"func\s+(Test[A-Za-z0-9_]+)\s*\(\s*t\s+\*testing\.T\s*\)", content)
    if not test_func_match:
        logging.debug(f"Skipping {src_path} - no Test function found")
        return None

    test_func_name = test_func_match.group(1)
    
    # Replace the signature
    content = content.replace(test_func_match.group(0), "func main()")

    # Inject trace initialization at the start of main()
    trace_init = inject_trace_header()
    # We find the start of main() function body
    main_func_start = content.find("func main()")
    if main_func_start == -1:
        return None
    
    brace_idx = content.find("{", main_func_start)
    if brace_idx == -1:
        return None
    
    content = content[:brace_idx + 1] + "\n" + trace_init + "\n" + content[brace_idx + 1:]

    # 5. Clean up testing references (t.Error, t.Fatal, etc.)
    content = re.sub(r"t\.Logf?\([^)]+\)", "fmt.Println()", content)
    content = re.sub(r"t\.Errorf?\(([^)]+)\)", r"panic(\1)", content)
    content = re.sub(r"t\.Fatalf?\(([^)]+)\)", r"panic(\1)", content)
    content = re.sub(r"t\.Skip\([^)]*\)", "return", content)
    content = re.sub(r"t\s+\*testing\.T", "", content)

    # 6. Add WEAVE_META header
    expected_nd = "medium"
    concurrency_pattern = "channel"
    if "mutex" in content.lower() or "sync.mutex" in content.lower() or "sync.rwmutex" in content.lower():
        concurrency_pattern = "mutex"
    elif "select" in content.lower():
        concurrency_pattern = "select"

    meta = f"""// WEAVE_META
// outcome: {outcome}
// concurrency_pattern: {concurrency_pattern}
// goroutine_count: 3
// expected_nondeterminism: {expected_nd}
// description: Human-written GoBench bug kernel {project}_{bug_id} ({outcome})"""

    return f"{meta}\n\n{content}"


def import_all():
    """Crawls GoBench/GoKer, converts tests to main, verifies compilation, and saves."""
    if not os.path.exists(GOBENCH_GOKER_DIR):
        logging.error(f"GoBench Goker directory not found at: {GOBENCH_GOKER_DIR}. Make sure gobench_temp is cloned.")
        sys.exit(1)

    os.makedirs(PROGRAMS_DIR, exist_ok=True)
    imported_count = 0

    # GoBench Goker is structured as: goker/<category>/<project>/<bug_id>/<file>.go
    # where category is either 'blocking' or 'nonblocking'
    for category in ["blocking", "nonblocking"]:
        cat_path = os.path.join(GOBENCH_GOKER_DIR, category)
        if not os.path.exists(cat_path):
            continue

        outcome = "leak" if category == "blocking" else "race"

        for project in sorted(os.listdir(cat_path)):
            proj_path = os.path.join(cat_path, project)
            if not os.path.isdir(proj_path):
                continue

            for bug_id in sorted(os.listdir(proj_path)):
                bug_path = os.path.join(proj_path, bug_id)
                if not os.path.isdir(bug_path):
                    continue

                # Look for *_test.go files inside the bug folder
                test_files = glob.glob(os.path.join(bug_path, "*_test.go"))
                if not test_files:
                    continue

                for tf in test_files:
                    instrumented_code = instrument_goker_file(tf, project, bug_id, outcome)
                    if not instrumented_code:
                        continue

                    # Write to temporary file for compilation verification
                    dest_file_name = f"goker_{project}_{bug_id}.go"
                    dest_path = os.path.join(PROGRAMS_DIR, dest_file_name)

                    with open(dest_path, "w") as f:
                        f.write(instrumented_code)

                    # Validate compilation
                    if verify_compilation(dest_path):
                        imported_count += 1
                        logging.info(f"Imported human-written GoBench bug: {dest_file_name}")
                    else:
                        # Remove if compilation fails (e.g. requires external packages)
                        if os.path.exists(dest_path):
                            os.remove(dest_path)

    logging.info(f"Import finished: {imported_count} human-written GoBench bug kernels successfully imported to {PROGRAMS_DIR}")


if __name__ == "__main__":
    import_all()
