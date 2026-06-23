// build_p20 generates the Phase-20 enriched dataset by compiling and running all
// programs under programs/instrumented/ and writing split files to dataset/output/.
//
// Each instrumented program is built once and run 5 times. ParseTrace now reads
// EventLog("weave-sync") events inline, so the resulting snapshots have populated
// Channels and Mutexes maps — the enriched state needed for the GoUnblock A/B experiment.
//
// Program IDs:
//
//	p20_<dirname>     → train split (prepare_trajectory.py's default)
//	p20val_<dirname>  → val split (held-out instrumented eval set)
//
// Val programs are any directory whose name appears in the valDirs set below.
//
// Usage:
//
//	go run ./cmd/build_p20/
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
	"strings"
	"sync"
	"time"
	"weave/tracer"
)

const (
	instrDir   = "programs/instrumented"
	outputDir  = "dataset/output"
	runsPerProg = 5
	minEvents  = 4
)

// valDirs are held out as the instrumented val set for the GoUnblock A/B metric.
// Everything else goes to train.
var valDirs = map[string]bool{
	"02_multiple":  true,
	"21_done_leak": true,
}

// WeaveMetadata and EvalExample mirror the types in dataset/schema.go so this
// command can live outside the dataset package without an import cycle.
type WeaveMetadata struct {
	Outcome                string
	ConcurrencyPattern     string
	GoroutineCount         int
	ExpectedNondeterminism string
	Description            string
}

type EvalExample struct {
	ProgramID          string                 `json:"program_id"`
	ProgramSource      string                 `json:"program_source"`
	PartialTrace       []tracer.StateSnapshot `json:"partial_trace"`
	NextEvent          *tracer.StateSnapshot  `json:"next_event"`
	FullOutcome        string                 `json:"full_outcome"`
	ConcurrencyPattern string                 `json:"concurrency_pattern"`
	GoroutineCount     int                    `json:"goroutine_count"`
	Nondeterminism     string                 `json:"nondeterminism"`
	RunIndex           int                    `json:"run_index"`
	SplitPercent       int                    `json:"split_percent"`
	RaceOutput         string                 `json:"race_output,omitempty"`
	TimedOut           bool                   `json:"timed_out"`
}

type task struct {
	dir    string // e.g. programs/instrumented/01_chan
	name   string // e.g. 01_chan
	id     string // p20_01_chan or p20val_01_chan
	meta   *WeaveMetadata
	source []byte
}

type result struct {
	id       string
	runs     int
	examples int
	errors   int
}

func main() {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		log.Fatalf("create output dir: %v", err)
	}

	dirs, err := findInstrumentedDirs(instrDir)
	if err != nil {
		log.Fatalf("find instrumented dirs: %v", err)
	}
	log.Printf("found %d instrumented programs in %s", len(dirs), instrDir)

	var tasks []task
	for _, d := range dirs {
		name := filepath.Base(d)
		mainFile := filepath.Join(d, "main.go")

		meta, err := parseWeaveMeta(mainFile)
		if err != nil {
			log.Printf("SKIP %s: %v", d, err)
			continue
		}
		source, err := os.ReadFile(mainFile)
		if err != nil {
			log.Printf("SKIP %s: read source: %v", d, err)
			continue
		}

		prefix := "p20_"
		if valDirs[name] {
			prefix = "p20val_"
		}
		tasks = append(tasks, task{
			dir:    d,
			name:   name,
			id:     prefix + name,
			meta:   meta,
			source: source,
		})
	}

	numWorkers := runtime.NumCPU()
	if numWorkers < 1 {
		numWorkers = 1
	}
	log.Printf("running with %d workers", numWorkers)

	tasksCh := make(chan task, len(tasks))
	resultsCh := make(chan result, len(tasks))

	var wg sync.WaitGroup
	for range numWorkers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for t := range tasksCh {
				resultsCh <- processTask(t)
			}
		}()
	}
	for _, t := range tasks {
		tasksCh <- t
	}
	close(tasksCh)

	var summary []result
	var collectWg sync.WaitGroup
	collectWg.Add(1)
	go func() {
		defer collectWg.Done()
		for range tasks {
			summary = append(summary, <-resultsCh)
		}
	}()

	wg.Wait()
	close(resultsCh)
	collectWg.Wait()

	sort.Slice(summary, func(i, j int) bool { return summary[i].id < summary[j].id })
	printSummary(summary)
}

func processTask(t task) result {
	r := result{id: t.id}

	timeout := 5 * time.Second
	if t.meta.Outcome == "deadlock" {
		// True deadlocks stall forever — short timeout is appropriate.
		timeout = 500 * time.Millisecond
	} else if t.meta.Outcome == "leak" {
		// Leak programs finish main() (50ms sleep) but leave goroutines blocked.
		// Allow 3s so the program completes even under heavy parallel load.
		timeout = 3 * time.Second
	}

	binDir := filepath.Join(outputDir, "_tmp", t.id, "bin")
	binaryPath := filepath.Join(binDir, t.id)
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		log.Printf("[%s] mkdir: %v", t.id, err)
		r.errors += runsPerProg
		return r
	}

	// Build the package directory once.
	buildCmd := exec.Command("go", "build", "-race", "-o", binaryPath, "./"+t.dir)
	if out, err := buildCmd.CombinedOutput(); err != nil {
		log.Printf("[%s] build: %v\n%s", t.id, err, strings.TrimSpace(string(out)))
		r.errors += runsPerProg
		return r
	}
	log.Printf("[%s] built OK", t.id)

	for run := range runsPerProg {
		runDir := filepath.Join(outputDir, "_tmp", t.id, fmt.Sprintf("run%d", run))
		if err := os.MkdirAll(runDir, 0o755); err != nil {
			r.errors++
			continue
		}
		traceFile := filepath.Join(runDir, t.id+".trace")

		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		res, err := tracer.RunCompiledProgram(ctx, binaryPath, traceFile)
		cancel()

		if err != nil {
			log.Printf("[%s] run %d: %v", t.id, run, err)
			r.errors++
			continue
		}
		r.runs++

		if res.TimedOut {
			ex := EvalExample{
				ProgramID:          t.id,
				ProgramSource:      string(t.source),
				PartialTrace:       []tracer.StateSnapshot{},
				FullOutcome:        t.meta.Outcome,
				ConcurrencyPattern: t.meta.ConcurrencyPattern,
				GoroutineCount:     t.meta.GoroutineCount,
				Nondeterminism:     t.meta.ExpectedNondeterminism,
				RunIndex:           run,
				TimedOut:           true,
			}
			if err := writeExample(ex, t.id, run, 0); err != nil {
				r.errors++
			} else {
				r.examples++
			}
			continue
		}

		if _, statErr := os.Stat(traceFile); os.IsNotExist(statErr) {
			log.Printf("[%s] run %d: no trace file", t.id, run)
			continue
		}

		// ParseTrace now reads EventLog("weave-sync") inline — snapshots have
		// populated Channels/Mutexes maps automatically.
		snapshots, err := tracer.ParseTrace(traceFile)
		if err != nil {
			log.Printf("[%s] run %d: ParseTrace: %v", t.id, run, err)
			r.errors++
			continue
		}
		if len(snapshots) < minEvents {
			log.Printf("[%s] run %d: only %d events, skipping", t.id, run, len(snapshots))
			continue
		}

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
				ProgramID:          t.id,
				ProgramSource:      string(t.source),
				PartialTrace:       snapshots[:n],
				NextEvent:          &next,
				FullOutcome:        t.meta.Outcome,
				ConcurrencyPattern: t.meta.ConcurrencyPattern,
				GoroutineCount:     t.meta.GoroutineCount,
				Nondeterminism:     t.meta.ExpectedNondeterminism,
				RunIndex:           run,
				SplitPercent:       pct,
				RaceOutput:         res.RaceOutput,
			}
			if err := writeExample(ex, t.id, run, pct); err != nil {
				r.errors++
			} else {
				r.examples++
			}
		}
	}
	return r
}

func findInstrumentedDirs(root string) ([]string, error) {
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil, err
	}
	var dirs []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		main := filepath.Join(root, e.Name(), "main.go")
		if _, err := os.Stat(main); err == nil {
			dirs = append(dirs, filepath.Join(root, e.Name()))
		}
	}
	sort.Strings(dirs)
	return dirs, nil
}

func parseWeaveMeta(mainFile string) (*WeaveMetadata, error) {
	data, err := os.ReadFile(mainFile)
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
			break
		}
		content := strings.TrimSpace(strings.TrimPrefix(line, "//"))
		parts := strings.SplitN(content, ": ", 2)
		if len(parts) != 2 {
			continue
		}
		key, val := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		switch key {
		case "outcome":
			meta.Outcome = val; found++
		case "concurrency_pattern":
			meta.ConcurrencyPattern = val; found++
		case "goroutine_count":
			var n int
			if _, err := fmt.Sscanf(val, "%d", &n); err != nil {
				return nil, fmt.Errorf("goroutine_count not int: %q", val)
			}
			meta.GoroutineCount = n; found++
		case "expected_nondeterminism":
			meta.ExpectedNondeterminism = val; found++
		case "description":
			meta.Description = val; found++
		}
	}
	if found < 5 {
		return nil, fmt.Errorf("incomplete WEAVE_META: %d/5 fields", found)
	}
	return meta, nil
}

func writeExample(ex EvalExample, id string, run, pct int) error {
	var name string
	if ex.TimedOut {
		name = fmt.Sprintf("%s_run%d_deadlock.json", id, run)
	} else {
		name = fmt.Sprintf("%s_run%d_split%d.json", id, run, pct)
	}
	data, err := json.MarshalIndent(ex, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, name), data, 0o644)
}

func printSummary(rows []result) {
	total := struct{ runs, examples, errors int }{}
	fmt.Println()
	fmt.Printf("%-35s  %5s  %8s  %6s\n", "program", "runs", "examples", "errors")
	fmt.Println(strings.Repeat("-", 60))
	for _, r := range rows {
		fmt.Printf("%-35s  %5d  %8d  %6d\n", r.id, r.runs, r.examples, r.errors)
		total.runs += r.runs
		total.examples += r.examples
		total.errors += r.errors
	}
	fmt.Println(strings.Repeat("-", 60))
	fmt.Printf("%-35s  %5d  %8d  %6d\n", "TOTAL", total.runs, total.examples, total.errors)
	fmt.Printf("\n%d examples written to %s/\n", total.examples, outputDir)
}
