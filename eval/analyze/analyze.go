package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const analyzeResultsDir = "eval/results"

// resultRecord mirrors the fields in each *_result.json file.
type resultRecord struct {
	ProgramID              string          `json:"program_id"`
	RunIndex               int             `json:"run_index"`
	SplitPercent           int             `json:"split_percent"`
	FullOutcome            string          `json:"full_outcome"`
	ConcurrencyPattern     string          `json:"concurrency_pattern"`
	Nondeterminism         string          `json:"nondeterminism"`
	IsDeadlockExample      bool            `json:"is_deadlock_example"`
	GroundTruthEventType   string          `json:"ground_truth_event_type"`
	GroundTruthGoroutineID uint64          `json:"ground_truth_goroutine_id"`
	Predicted              *predictedEntry `json:"predicted"`
	CorrectEventType       *bool           `json:"correct_event_type"`
	CorrectGoroutineID     *bool           `json:"correct_goroutine_id"`
	Error                  string          `json:"error,omitempty"`
}

type predictedEntry struct {
	EventType   string `json:"event_type"`
	GoroutineID uint64 `json:"goroutine_id"`
	Reasoning   string `json:"reasoning"`
	Confidence  string `json:"confidence"`
}

// tally tracks correct/total counts for a single dimension.
type tally struct{ correct, total int }

func (t tally) pct() float64 {
	if t.total == 0 {
		return 0
	}
	return float64(t.correct) / float64(t.total) * 100
}

func main() {
	files, err := filepath.Glob(filepath.Join(analyzeResultsDir, "*_result.json"))
	if err != nil || len(files) == 0 {
		fmt.Fprintf(os.Stderr, "no result files found in %s — run eval/zero_shot.go first\n", analyzeResultsDir)
		os.Exit(1)
	}

	var records []resultRecord
	for _, f := range files {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		var r resultRecord
		if err := json.Unmarshal(data, &r); err != nil {
			continue
		}
		records = append(records, r)
	}

	// Partition into scored (has a next event) and deadlock/error records.
	var scored []resultRecord
	var deadlockExamples []resultRecord
	var errorRecords []resultRecord
	for _, r := range records {
		if r.Error != "" {
			errorRecords = append(errorRecords, r)
		} else if r.IsDeadlockExample || r.CorrectEventType == nil {
			deadlockExamples = append(deadlockExamples, r)
		} else {
			scored = append(scored, r)
		}
	}

	fmt.Printf("=== Weave Zero-Shot Eval — %d total examples ===\n\n", len(records))
	fmt.Printf("  Scored (non-deadlock, no error): %d\n", len(scored))
	fmt.Printf("  Deadlock/no-next-event:          %d\n", len(deadlockExamples))
	fmt.Printf("  Errors (API / parse failures):   %d\n\n", len(errorRecords))

	// --- Overall accuracy ---
	var overallET, overallGID tally
	for _, r := range scored {
		overallET.total++
		overallGID.total++
		if *r.CorrectEventType {
			overallET.correct++
		}
		if *r.CorrectGoroutineID {
			overallGID.correct++
		}
	}
	fmt.Printf("--- Overall accuracy (%d scored) ---\n", len(scored))
	fmt.Printf("  event_type:   %d/%d  (%.1f%%)\n", overallET.correct, overallET.total, overallET.pct())
	fmt.Printf("  goroutine_id: %d/%d  (%.1f%%)\n\n", overallGID.correct, overallGID.total, overallGID.pct())

	// --- By event type ---
	etMap := map[string]*tally{}
	for _, r := range scored {
		gt := r.GroundTruthEventType
		if etMap[gt] == nil {
			etMap[gt] = &tally{}
		}
		etMap[gt].total++
		if *r.CorrectEventType {
			etMap[gt].correct++
		}
	}
	fmt.Printf("--- Accuracy by ground-truth event type ---\n")
	printTallyMap(etMap)
	fmt.Println()

	// --- By concurrency pattern ---
	patMap := map[string]*tally{}
	for _, r := range scored {
		p := r.ConcurrencyPattern
		if patMap[p] == nil {
			patMap[p] = &tally{}
		}
		patMap[p].total++
		if *r.CorrectEventType {
			patMap[p].correct++
		}
	}
	fmt.Printf("--- event_type accuracy by concurrency pattern ---\n")
	printTallyMap(patMap)
	fmt.Println()

	// --- By nondeterminism level ---
	ndMap := map[string]*tally{}
	for _, r := range scored {
		n := r.Nondeterminism
		if ndMap[n] == nil {
			ndMap[n] = &tally{}
		}
		ndMap[n].total++
		if *r.CorrectEventType {
			ndMap[n].correct++
		}
	}
	fmt.Printf("--- event_type accuracy by nondeterminism level ---\n")
	printTallyMap(ndMap)
	fmt.Println()

	// --- By split percent ---
	spMap := map[string]*tally{}
	for _, r := range scored {
		k := fmt.Sprintf("%d%%", r.SplitPercent)
		if spMap[k] == nil {
			spMap[k] = &tally{}
		}
		spMap[k].total++
		if *r.CorrectEventType {
			spMap[k].correct++
		}
	}
	fmt.Printf("--- event_type accuracy by trace split point ---\n")
	printTallyMap(spMap)
	fmt.Println()

	// --- Confusion matrix ---
	eventTypes := []string{"GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"}
	// matrix[actual][predicted]
	matrix := map[string]map[string]int{}
	for _, et := range eventTypes {
		matrix[et] = map[string]int{}
	}
	for _, r := range scored {
		if r.Predicted == nil {
			continue
		}
		gt := r.GroundTruthEventType
		pred := r.Predicted.EventType
		if matrix[gt] == nil {
			matrix[gt] = map[string]int{}
		}
		matrix[gt][pred]++
	}
	fmt.Printf("--- Confusion matrix (rows=actual, cols=predicted) ---\n")
	fmt.Printf("%-12s", "actual\\pred")
	for _, et := range eventTypes {
		fmt.Printf("  %10s", shortET(et))
	}
	fmt.Println()
	fmt.Println(strings.Repeat("-", 12+len(eventTypes)*12))
	for _, actual := range eventTypes {
		rowTotal := 0
		for _, v := range matrix[actual] {
			rowTotal += v
		}
		if rowTotal == 0 {
			continue
		}
		fmt.Printf("%-12s", shortET(actual))
		for _, pred := range eventTypes {
			v := matrix[actual][pred]
			if v == 0 {
				fmt.Printf("  %10s", ".")
			} else {
				fmt.Printf("  %10d", v)
			}
		}
		fmt.Printf("  (n=%d)\n", rowTotal)
	}
	fmt.Println()

	// --- Deadlock / race detection ---
	fmt.Printf("--- Deadlock and race detection (soft check: does reasoning mention the issue?) ---\n")
	deadlockMentions := 0
	for _, r := range deadlockExamples {
		if r.Predicted != nil && strings.Contains(strings.ToLower(r.Predicted.Reasoning), "deadlock") {
			deadlockMentions++
		}
	}
	fmt.Printf("  Deadlock examples:    %d total\n", len(deadlockExamples))
	fmt.Printf("  Mentions 'deadlock':  %d/%d  (%.1f%%)\n\n",
		deadlockMentions, len(deadlockExamples), pctF(deadlockMentions, len(deadlockExamples)))

	var raceExamples []resultRecord
	for _, r := range scored {
		if r.FullOutcome == "race" {
			raceExamples = append(raceExamples, r)
		}
	}
	raceMentions := 0
	for _, r := range raceExamples {
		if r.Predicted != nil && strings.Contains(strings.ToLower(r.Predicted.Reasoning), "race") {
			raceMentions++
		}
	}
	fmt.Printf("  Race examples:        %d total\n", len(raceExamples))
	fmt.Printf("  Mentions 'race':      %d/%d  (%.1f%%)\n\n",
		raceMentions, len(raceExamples), pctF(raceMentions, len(raceExamples)))

	// --- Most common failures ---
	type failure struct {
		gt   string
		pred string
		cnt  int
	}
	failMap := map[string]int{}
	for _, r := range scored {
		if r.Predicted == nil || *r.CorrectEventType {
			continue
		}
		k := fmt.Sprintf("%s -> %s", r.GroundTruthEventType, r.Predicted.EventType)
		failMap[k]++
	}
	type kv struct {
		k string
		v int
	}
	var failList []kv
	for k, v := range failMap {
		failList = append(failList, kv{k, v})
	}
	sort.Slice(failList, func(i, j int) bool { return failList[i].v > failList[j].v })
	fmt.Printf("--- Most common event_type misclassifications ---\n")
	fmt.Printf("  %-30s  %5s\n", "actual -> predicted", "count")
	fmt.Println("  " + strings.Repeat("-", 38))
	for i, kv := range failList {
		if i >= 10 {
			break
		}
		fmt.Printf("  %-30s  %5d\n", kv.k, kv.v)
	}
	fmt.Println()

	// --- Confidence calibration ---
	confMap := map[string]*tally{}
	for _, r := range scored {
		if r.Predicted == nil {
			continue
		}
		c := r.Predicted.Confidence
		if confMap[c] == nil {
			confMap[c] = &tally{}
		}
		confMap[c].total++
		if *r.CorrectEventType {
			confMap[c].correct++
		}
	}
	fmt.Printf("--- event_type accuracy by model confidence ---\n")
	printTallyMap(confMap)
	fmt.Println()
}

func printTallyMap(m map[string]*tally) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		t := m[k]
		bar := progressBar(t.correct, t.total, 20)
		fmt.Printf("  %-20s  %3d/%3d  %5.1f%%  %s\n", k, t.correct, t.total, t.pct(), bar)
	}
}

func progressBar(correct, total, width int) string {
	if total == 0 {
		return strings.Repeat("░", width)
	}
	filled := correct * width / total
	return strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
}

func shortET(et string) string {
	return strings.TrimPrefix(et, "Go")
}

func pctF(n, d int) float64 {
	if d == 0 {
		return 0
	}
	return float64(n) / float64(d) * 100
}
