#!/usr/bin/env python3
"""
dataset/generate_programs.py

Synthesizes new concurrent Go programs of varying structures (worker pools,
producer-consumer, shared resources, pipelines, selects) with randomized
parameters (goroutines, buffers, sleeps) and optional concurrency bugs
(leaks, deadlocks, races).

Generates compiling Go files with standard WEAVE_META comments and trace
headers, and saves them to programs/ with names gen_XX_<pattern>.go.

Run:
  .venv/bin/python dataset/generate_programs.py --count 50
"""

import os
import sys
import random
import argparse
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


# ---------------------------------------------------------------------------
# Concurrency Templates
# ---------------------------------------------------------------------------


def make_worker_pool(idx: int, inject_bug: bool) -> str:
    """Generates a worker pool Go program."""
    num_workers = random.randint(2, 5)
    num_jobs = random.randint(5, 12)
    buffer_cap = random.choice([0, 1, 2, 5])
    
    outcome = "leak" if inject_bug else "success"
    pattern = "channel"
    expected_nd = "medium" if num_workers > 2 else "low"
    
    meta = f"""// WEAVE_META
// outcome: {outcome}
// concurrency_pattern: {pattern}
// goroutine_count: {num_workers + 1}
// expected_nondeterminism: {expected_nd}
// description: Randomized worker pool with W={num_workers}, J={num_jobs}, Cap={buffer_cap}, leak_bug={inject_bug}"""

    trace_start = inject_trace_header()

    close_statement = "// bug: close(jobs) omitted to cause leak" if inject_bug else "close(jobs)"

    code = f"""package main

import (
\t"fmt"
\t"os"
\t"runtime/trace"
\t"sync"
\t"time"
)

func worker(id int, jobs <-chan int, wg *sync.WaitGroup) {{
\tdefer wg.Done()
\tfor job := range jobs {{
\t\t_ = job
\t\t// Simulate processing workload
\t\ttime.Sleep(time.Millisecond * 2)
\t}}
}}

func main() {{
{trace_start}

\tjobs := make(chan int, {buffer_cap})
\tvar wg sync.WaitGroup

\t// Start workers
\tfor w := 1; w <= {num_workers}; w++ {{
\t\twg.Add(1)
\t\tgo worker(w, jobs, &wg)
\t}}

\t// Send jobs
\tfor j := 1; j <= {num_jobs}; j++ {{
\t\tjobs <- j
\t}}
\t{close_statement}

\t// Wait for completion (will block forever if jobs channel is not closed)
\t// WaitGroup placement is correct, but leak occurs inside worker range.
\t// To ensure program exits in leak case for trace collection, we use a timeout.
\t
\t// Create channel to notify main
\tdone := make(chan struct{{}})
\tgo func() {{
\t\twg.Wait()
\t\tclose(done)
\t}}()

\tselect {{
\tcase <-done:
\t\tfmt.Println("success")
\tcase <-time.After(250 * time.Millisecond):
\t\t// If leaked, we exit cleanly so runtime trace stops and we save it.
\t\tfmt.Println("timeout")
\t}}
}}
"""
    return f"{meta}\n\n{code}"


def make_producer_consumer(idx: int, inject_bug: bool) -> str:
    """Generates a producer-consumer Go program."""
    num_producers = random.randint(2, 4)
    buffer_cap = random.choice([0, 2, 5])
    
    # Bug: omit closing channel -> consumer leaks
    outcome = "leak" if inject_bug else "success"
    pattern = "channel"
    expected_nd = "medium" if num_producers > 2 else "low"
    
    meta = f"""// WEAVE_META
// outcome: {outcome}
// concurrency_pattern: {pattern}
// goroutine_count: {num_producers + 2}
// expected_nondeterminism: {expected_nd}
// description: Producer-consumer queue with P={num_producers}, Cap={buffer_cap}, leak_bug={inject_bug}"""

    trace_start = inject_trace_header()

    close_stmt = "// close omitted to cause leak" if inject_bug else "close(ch)"

    code = f"""package main

import (
\t"fmt"
\t"os"
\t"runtime/trace"
\t"sync"
\t"time"
)

func producer(id int, ch chan<- int, wg *sync.WaitGroup) {{
\tdefer wg.Done()
\tfor i := 0; i < 3; i++ {{
\t\tch <- id*10 + i
\t\ttime.Sleep(time.Millisecond * 1)
\t}}
}}

func main() {{
{trace_start}

\tch := make(chan int, {buffer_cap})
\tvar pwg sync.WaitGroup
\tvar cwg sync.WaitGroup

\t// Start producers
\tfor p := 1; p <= {num_producers}; p++ {{
\t\tpwg.Add(1)
\t\tgo producer(p, ch, &pwg)
\t}}

\t// Start consumer
\tcwg.Add(1)
\tgo func() {{
\t\tdefer cwg.Done()
\t\tfor val := range ch {{
\t\t\t_ = val
\t\t}}
\t}}()

\t// Closer goroutine
\tgo func() {{
\t\tpwg.Wait()
\t\t{close_stmt}
\t}}()

\t// Monitor
\tdone := make(chan struct{{}})
\tgo func() {{
\t\tcwg.Wait()
\t\tclose(done)
\t}}()

\tselect {{
\tcase <-done:
\t\tfmt.Println("success")
\tcase <-time.After(200 * time.Millisecond):
\t\tfmt.Println("timeout")
\t}}
}}
"""
    return f"{meta}\n\n{code}"


def make_shared_lock(idx: int, inject_bug: bool) -> str:
    """Generates a shared state read/write program (mutex vs data race)."""
    num_workers = random.randint(3, 6)
    
    # Bug: concurrency map writes without mutex (data race)
    outcome = "race" if inject_bug else "success"
    pattern = "mutex"
    expected_nd = "high"
    
    meta = f"""// WEAVE_META
// outcome: {outcome}
// concurrency_pattern: {pattern}
// goroutine_count: {num_workers + 1}
// expected_nondeterminism: {expected_nd}
// description: Concurrent map access with W={num_workers}, race_bug={inject_bug}"""

    trace_start = inject_trace_header()

    lock_stmt = "// lock omitted to trigger race" if inject_bug else "mu.Lock()"
    unlock_stmt = "// unlock omitted" if inject_bug else "mu.Unlock()"

    code = f"""package main

import (
\t"fmt"
\t"os"
\t"runtime/trace"
\t"sync"
\t"time"
)

func main() {{
{trace_start}

\tvar mu sync.Mutex
\t_ = mu // prevent declared and not used error
\tsharedMap := make(map[int]int)
\tvar wg sync.WaitGroup

\tfor w := 0; w < {num_workers}; w++ {{
\t\twg.Add(1)
\t\tgo func(id int) {{
\t\t\tdefer wg.Done()
\t\t\tfor i := 0; i < 5; i++ {{
\t\t\t\t{lock_stmt}
\t\t\t\tsharedMap[id] = id * i
\t\t\t\t{unlock_stmt}
\t\t\t\ttime.Sleep(time.Microsecond * 50)
\t\t\t}}
\t\t}}(w)
\t}}

\twg.Wait()
\tfmt.Println("completed map writes, length:", len(sharedMap))
}}
"""
    return f"{meta}\n\n{code}"


def make_timeout_select(idx: int, inject_bug: bool) -> str:
    """Generates a select-timeout leak program (select-block class)."""
    # Bug: unbuffered channel + select statement where channel is never read
    # if timeout triggers -> goroutine leaks forever on write block.
    outcome = "leak" if inject_bug else "success"
    pattern = "select"
    expected_nd = "low"
    
    meta = f"""// WEAVE_META
// outcome: {outcome}
// concurrency_pattern: {pattern}
// goroutine_count: 2
// expected_nondeterminism: {expected_nd}
// description: Select statement on unbuffered channel, leak_bug={inject_bug}"""

    trace_start = inject_trace_header()

    if inject_bug:
        # Unbuffered channel causes writer to block forever if timeout exits first.
        make_chan_stmt = "ch := make(chan int)"
    else:
        # Buffered channel allows writer to finish even if timeout exits first.
        make_chan_stmt = "ch := make(chan int, 1)"

    code = f"""package main

import (
\t"fmt"
\t"os"
\t"runtime/trace"
\t"time"
)

func main() {{
{trace_start}

\t{make_chan_stmt}

\tgo func() {{
\t\t// Simulate processing delay
\t\ttime.Sleep(time.Millisecond * 10)
\t\tch <- 42
\t}}()

\tselect {{
\tcase val := <-ch:
\t\tfmt.Println("received:", val)
\tcase <-time.After(1 * time.Millisecond):
\t\tfmt.Println("timeout occurred")
\t}}

\t// Small delay to allow the leaked goroutine to lock into GoWaiting block
\ttime.Sleep(time.Millisecond * 20)
}}
"""
    return f"{meta}\n\n{code}"


def make_pipeline(idx: int, inject_bug: bool) -> str:
    """Generates a multi-stage concurrency pipeline Go program."""
    outcome = "leak" if inject_bug else "success"
    pattern = "pipeline"
    expected_nd = "medium"
    
    meta = f"""// WEAVE_META
// outcome: {outcome}
// concurrency_pattern: {pattern}
// goroutine_count: 4
// expected_nondeterminism: {expected_nd}
// description: Pipeline pipeline stages stage1 -> stage2 -> stage3, leak_bug={inject_bug}"""

    trace_start = inject_trace_header()

    # Bug: stage3 exits early without draining stage2, causing stage2/stage1 to block on send.
    drain_stmt = "for range inCh { /* normal drain */ }"
    if inject_bug:
        drain_stmt = """\t// Bug: exit early after 1 item, leaving stage2 blocked
\tval := <-inCh
\t_ = val"""

    code = f"""package main

import (
\t"fmt"
\t"os"
\t"runtime/trace"
\t"sync"
\t"time"
)

func stage1(out chan<- int, wg *sync.WaitGroup) {{
\tdefer wg.Done()
\tfor i := 0; i < 5; i++ {{
\t\tout <- i
\t\ttime.Sleep(time.Millisecond * 1)
\t}}
\tclose(out)
}}

func stage2(in <-chan int, out chan<- int, wg *sync.WaitGroup) {{
\tdefer wg.Done()
\tfor v := range in {{
\t\tout <- v * 2
\t\ttime.Sleep(time.Millisecond * 1)
\t}}
\tclose(out)
}}

func main() {{
{trace_start}

\tvar wg1, wg2, wg3 sync.WaitGroup
\tch1 := make(chan int)
\tch2 := make(chan int)

\twg1.Add(1)
\tgo stage1(ch1, &wg1)

\twg2.Add(1)
\tgo stage2(ch1, ch2, &wg2)

\twg3.Add(1)
\tgo func(inCh <-chan int) {{
\t\tdefer wg3.Done()
\t\t{drain_stmt}
\t}}(ch2)

\t// Exit harness
\tdone := make(chan struct{{}})
\tgo func() {{
\t\twg1.Wait()
\t\twg2.Wait()
\t\twg3.Wait()
\t\tclose(done)
\t}}()

\tselect {{
\tcase <-done:
\t\tfmt.Println("pipeline done")
\tcase <-time.After(200 * time.Millisecond):
\t\tfmt.Println("pipeline timeout")
\t}}
}}
"""
    return f"{meta}\n\n{code}"


# ---------------------------------------------------------------------------
# Program Compilation Verification
# ---------------------------------------------------------------------------


def verify_compilation(file_path: str) -> bool:
    """Verifies that the generated Go file compiles cleanly using go build."""
    try:
        # Search for standard Go locations on macOS/Unix if "go" is not in PATH
        go_bin = "go"
        for path in ["/opt/homebrew/bin/go", "/usr/local/bin/go"]:
            if os.path.exists(path):
                go_bin = path
                break

        # Run go build in a temp directory or target path
        res = subprocess.run(
            [go_bin, "build", "-o", os.devnull, file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return True
        else:
            logging.warning(f"Compilation failed for {file_path}: {res.stderr}")
            return False
    except Exception as e:
        logging.error(f"Error executing go build: {e}")
        return False


# ---------------------------------------------------------------------------
# Main Generation loop
# ---------------------------------------------------------------------------


def generate_all(count: int):
    """Generates the requested number of parameterized programs, checking compilation."""
    os.makedirs(PROGRAMS_DIR, exist_ok=True)
    
    generators = [
        ("workerpool", make_worker_pool),
        ("prodcons", make_producer_consumer),
        ("sharedlock", make_shared_lock),
        ("selecttimeout", make_timeout_select),
        ("pipeline", make_pipeline)
    ]

    generated_count = 0
    attempts = 0
    max_attempts = count * 3  # safety threshold to prevent infinite loop

    logging.info(f"Initiating synthesis of {count} concurrent Go programs in {PROGRAMS_DIR}")

    while generated_count < count and attempts < max_attempts:
        attempts += 1
        
        # Pick a template type
        pattern_name, gen_func = random.choice(generators)
        
        # Decide bug status (approx. 50% bug injection rate)
        inject_bug = random.choice([True, False])
        
        idx = generated_count + 1
        code_content = gen_func(idx, inject_bug)
        
        file_name = f"gen_{idx:03d}_{pattern_name}.go"
        file_path = os.path.join(PROGRAMS_DIR, file_name)

        # Write to temporary file for verification
        with open(file_path, "w") as f:
            f.write(code_content)

        # Verify compilation
        if verify_compilation(file_path):
            generated_count += 1
            logging.info(f"Synthesized program {generated_count}/{count}: {file_name} (bug={inject_bug})")
        else:
            # Delete if compilation failed
            if os.path.exists(file_path):
                os.remove(file_path)

    logging.info(f"Synthesis finished: {generated_count} programs successfully generated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Parameterized Concurrent Go Program Generator")
    parser.add_argument("--count", type=int, default=50, help="Number of programs to synthesize")
    args = parser.parse_args()

    generate_all(args.count)
