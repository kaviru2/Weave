package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
	"weave/tracer"
)

const (
	programsDir = "programs"
	outputDir   = "dataset/output"
	runsPerProg = 5
	minEvents   = 4 // skip traces with fewer events — not enough to split
)

// summaryRow holds per-program stats for the final printed table.
type summaryRow struct {
	id       string
	runs     int
	examples int
	errors   int
}

// workTask represents a Go program that needs to be compiled and traced.
type workTask struct {
	srcFile string
	meta    *WeaveMetadata
	source  []byte
	id      string
}

func main() {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		log.Fatalf("create output dir: %v", err)
	}

	programs, err := findPrograms(programsDir)
	if err != nil {
		log.Fatalf("find programs: %v", err)
	}
	log.Printf("found %d programs in %s", len(programs), programsDir)

	// Determine worker count
	numWorkers := runtime.NumCPU()
	if numWorkers < 1 {
		numWorkers = 1
	}
	log.Printf("launching concurrency worker pool with %d workers", numWorkers)

	tasks := make([]workTask, 0, len(programs))
	for _, srcFile := range programs {
		meta, err := parseWeaveMeta(srcFile)
		if err != nil {
			log.Printf("SKIP %s: parse meta: %v", srcFile, err)
			continue
		}
		source, err := os.ReadFile(srcFile)
		if err != nil {
			log.Printf("SKIP %s: read source: %v", srcFile, err)
			continue
		}

		tasks = append(tasks, workTask{
			srcFile: srcFile,
			meta:    meta,
			source:  source,
			id:      programID(srcFile),
		})
	}

	tasksChan := make(chan workTask, len(tasks))
	resultsChan := make(chan summaryRow, len(tasks))

	// Start worker pool
	var wg sync.WaitGroup
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for t := range tasksChan {
				resultsChan <- processTask(t)
			}
		}()
	}

	// Feed tasks to workers
	for _, t := range tasks {
		tasksChan <- t
	}
	close(tasksChan)

	// Wait for all workers to finish in a separate goroutine
	var wgWait sync.WaitGroup
	wgWait.Add(1)
	var summary []summaryRow
	go func() {
		defer wgWait.Done()
		for i := 0; i < len(tasks); i++ {
			r := <-resultsChan
			summary = append(summary, r)
		}
	}()

	wg.Wait()
	close(resultsChan)
	wgWait.Wait()

	// Sort summary rows to keep output stable
	sort.Slice(summary, func(i, j int) bool {
		return summary[i].id < summary[j].id
	})

	printSummary(summary)
}

// processTask compiles the source file once and runs it 5 times.
func processTask(task workTask) summaryRow {
	id := task.id
	meta := task.meta
	source := task.source
	srcFile := task.srcFile

	timeout := 5 * time.Second
	if meta.Outcome == "deadlock" {
		// Short timeout: enough for a few trace events before the program stalls.
		timeout = 500 * time.Millisecond
	}

	r := summaryRow{id: id}

	// 1. Compile the program exactly ONCE per program
	binDir := filepath.Join(outputDir, "_tmp", id, "bin")
	binaryPath := filepath.Join(binDir, id)

	if err := os.MkdirAll(binDir, 0o755); err != nil {
		log.Printf("[%s] failed to create bin dir: %v", id, err)
		r.errors += runsPerProg
		return r
	}

	goBin := "go"
	if _, err := exec.LookPath("go"); err != nil {
		if _, errHomebrew := os.Stat("/opt/homebrew/bin/go"); errHomebrew == nil {
			goBin = "/opt/homebrew/bin/go"
		}
	}

	buildCmd := exec.Command(goBin, "build", "-race", "-o", binaryPath, srcFile)
	if out, err := buildCmd.CombinedOutput(); err != nil {
		log.Printf("[%s] build error: %v\n%s", id, err, strings.TrimSpace(string(out)))
		r.errors += runsPerProg
		return r
	}

	// 2. Execute the pre-built binary runsPerProg times
	for run := 0; run < runsPerProg; run++ {
		runOutputDir := filepath.Join(outputDir, "_tmp", id, fmt.Sprintf("run%d", run))
		if err := os.MkdirAll(runOutputDir, 0o755); err != nil {
			log.Printf("  [%s] run %d: create output dir error: %v", id, run, err)
			r.errors++
			continue
		}

		traceFile := filepath.Join(runOutputDir, id+".trace")

		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		result, err := tracer.RunCompiledProgram(ctx, binaryPath, traceFile)
		cancel()

		if err != nil {
			log.Printf("  [%s] run %d: RunCompiledProgram error: %v", id, run, err)
			r.errors++
			continue
		}

		r.runs++

		if result.TimedOut {
			// Deadlock: emit a single example with no trace.
			ex := EvalExample{
				ProgramID:          id,
				ProgramSource:      string(source),
				PartialTrace:       []tracer.StateSnapshot{},
				NextEvent:          nil,
				FullOutcome:        meta.Outcome,
				ConcurrencyPattern: meta.ConcurrencyPattern,
				GoroutineCount:     meta.GoroutineCount,
				Nondeterminism:     meta.ExpectedNondeterminism,
				RunIndex:           run,
				SplitPercent:       0,
				RaceOutput:         result.RaceOutput,
				TimedOut:           true,
			}
			if err := writeExample(ex, id, run, 0); err != nil {
				log.Printf("  [%s] run %d: write deadlock example: %v", id, run, err)
				r.errors++
			} else {
				r.examples++
			}
			continue
		}

		// Parse the trace file if it exists.
		if _, statErr := os.Stat(result.TraceFile); os.IsNotExist(statErr) {
			log.Printf("  [%s] run %d: no trace file at %s", id, run, result.TraceFile)
			continue
		}

		snapshots, err := tracer.ParseTrace(result.TraceFile)
		if err != nil {
			log.Printf("  [%s] run %d: ParseTrace: %v", id, run, err)
			r.errors++
			continue
		}

		if len(snapshots) < minEvents {
			log.Printf("  [%s] run %d: only %d events — skipping (< %d)", id, run, len(snapshots), minEvents)
			continue
		}

		// Emit 3 examples: at 25%, 50%, 75% split points.
		for _, pct := range []int{25, 50, 75} {
			n := len(snapshots) * pct / 100
			if n == 0 {
				n = 1
			}
			if n >= len(snapshots) {
				n = len(snapshots) - 1
			}
			next := snapshots[n]
			ex := EvalExample{
				ProgramID:          id,
				ProgramSource:      string(source),
				PartialTrace:       snapshots[:n],
				NextEvent:          &next,
				FullOutcome:        meta.Outcome,
				ConcurrencyPattern: meta.ConcurrencyPattern,
				GoroutineCount:     meta.GoroutineCount,
				Nondeterminism:     meta.ExpectedNondeterminism,
				RunIndex:           run,
				SplitPercent:       pct,
				RaceOutput:         result.RaceOutput,
				TimedOut:           false,
			}
			if err := writeExample(ex, id, run, pct); err != nil {
				log.Printf("  [%s] run %d split %d%%: write error: %v", id, run, pct, err)
				r.errors++
			} else {
				r.examples++
			}
		}
	}

	return r
}

// findPrograms returns all *.go files in dir, sorted by name.
func findPrograms(dir string) ([]string, error) {
	entries, err := filepath.Glob(filepath.Join(dir, "*.go"))
	if err != nil {
		return nil, err
	}
	sort.Strings(entries)
	return entries, nil
}

// programID derives a short identifier from a file path, e.g. "01_simple_channel".
func programID(srcFile string) string {
	base := filepath.Base(srcFile)
	return strings.TrimSuffix(base, filepath.Ext(base))
}

// parseWeaveMeta reads the // WEAVE_META block at the top of a Go source file.
func parseWeaveMeta(srcFile string) (*WeaveMetadata, error) {
	data, err := os.ReadFile(srcFile)
	if err != nil {
		return nil, err
	}

	lines := strings.Split(string(data), "\n")
	inMeta := false
	meta := &WeaveMetadata{}
	found := 0

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "// WEAVE_META" {
			inMeta = true
			continue
		}
		if !inMeta {
			continue
		}
		if !strings.HasPrefix(line, "//") {
			break // end of comment block
		}
		content := strings.TrimPrefix(line, "//")
		content = strings.TrimSpace(content)
		parts := strings.SplitN(content, ": ", 2)
		if len(parts) != 2 {
			continue
		}
		key, val := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		switch key {
		case "outcome":
			meta.Outcome = val
			found++
		case "concurrency_pattern":
			meta.ConcurrencyPattern = val
			found++
		case "goroutine_count":
			n, err := strconv.Atoi(val)
			if err != nil {
				return nil, fmt.Errorf("goroutine_count not an int: %q", val)
			}
			meta.GoroutineCount = n
			found++
		case "expected_nondeterminism":
			meta.ExpectedNondeterminism = val
			found++
		case "description":
			meta.Description = val
			found++
		}
	}

	if found < 5 {
		return nil, fmt.Errorf("incomplete WEAVE_META block: only %d/5 fields found", found)
	}
	return meta, nil
}

// writeExample serialises an EvalExample to dataset/output/<id>_run<N>_split<P>.json.
func writeExample(ex EvalExample, id string, run, pct int) error {
	var name string
	if ex.TimedOut {
		name = fmt.Sprintf("%s_run%d_deadlock.json", id, run)
	} else {
		name = fmt.Sprintf("%s_run%d_split%d.json", id, run, pct)
	}
	path := filepath.Join(outputDir, name)

	data, err := json.MarshalIndent(ex, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

// printSummary prints a table of program, runs completed, examples produced, errors.
func printSummary(rows []summaryRow) {
	total := struct{ runs, examples, errors int }{}
	fmt.Println()
	fmt.Printf("%-30s  %5s  %8s  %6s\n", "program", "runs", "examples", "errors")
	fmt.Println(strings.Repeat("-", 56))
	for _, r := range rows {
		fmt.Printf("%-30s  %5d  %8d  %6d\n", r.id, r.runs, r.examples, r.errors)
		total.runs += r.runs
		total.examples += r.examples
		total.errors += r.errors
	}
	fmt.Println(strings.Repeat("-", 56))
	fmt.Printf("%-30s  %5d  %8d  %6d\n", "TOTAL", total.runs, total.examples, total.errors)
	fmt.Printf("\n%d examples written to %s/\n", total.examples, outputDir)
}
