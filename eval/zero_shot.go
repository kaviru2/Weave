package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"weave/tracer"

	"github.com/joho/godotenv"
	"google.golang.org/genai"
)

const (
	datasetDir  = "dataset/output"
	resultsDir  = "eval/results"
	concurrency = 10 // max in-flight API requests
)

// evalExample mirrors the JSON fields we need from dataset/output/*.json.
// We re-declare only the fields we use to avoid importing the dataset package.
type evalExample struct {
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

// predictedEvent is what we ask the model to return.
type predictedEvent struct {
	EventType   string `json:"event_type"`
	GoroutineID uint64 `json:"goroutine_id"`
	Reasoning   string `json:"reasoning"`
	Confidence  string `json:"confidence"`
}

// evalResult is one scored record written to eval/results/.
type evalResult struct {
	ProgramID              string          `json:"program_id"`
	RunIndex               int             `json:"run_index"`
	SplitPercent           int             `json:"split_percent"`
	FullOutcome            string          `json:"full_outcome"`
	ConcurrencyPattern     string          `json:"concurrency_pattern"`
	Nondeterminism         string          `json:"nondeterminism"`
	IsDeadlockExample      bool            `json:"is_deadlock_example"`
	GroundTruthEventType   string          `json:"ground_truth_event_type"`
	GroundTruthGoroutineID uint64          `json:"ground_truth_goroutine_id"`
	Predicted              *predictedEvent `json:"predicted"`
	CorrectEventType       *bool           `json:"correct_event_type"`   // nil for deadlock examples
	CorrectGoroutineID     *bool           `json:"correct_goroutine_id"` // nil for deadlock examples
	RawResponse            string          `json:"raw_response"`
	Error                  string          `json:"error,omitempty"`
}

func main() {
	// Load .env so GEMINI_API_KEY and MODEL are available via os.Getenv.
	if err := godotenv.Load(); err != nil {
		log.Printf("note: no .env file found (%v) — relying on environment variables", err)
	}

	apiKey := os.Getenv("GEMINI_API_KEY")
	if apiKey == "" {
		log.Fatal("GEMINI_API_KEY is not set")
	}
	modelName := os.Getenv("MODEL")
	if modelName == "" {
		modelName = "gemini-3.5-flash"
	}

	ctx := context.Background()
	client, err := genai.NewClient(ctx, &genai.ClientConfig{APIKey: apiKey})
	if err != nil {
		log.Fatalf("create Gemini client: %v", err)
	}

	if err := os.MkdirAll(resultsDir, 0o755); err != nil {
		log.Fatalf("create results dir: %v", err)
	}

	files, err := filepath.Glob(filepath.Join(datasetDir, "*.json"))
	if err != nil || len(files) == 0 {
		log.Fatalf("no examples found in %s", datasetDir)
	}
	sort.Strings(files)
	log.Printf("found %d examples — model: %s — concurrency: %d", len(files), modelName, concurrency)

	var (
		sem      = make(chan struct{}, concurrency)
		wg       sync.WaitGroup
		done     atomic.Int64
		errCount atomic.Int64
		total    = int64(len(files))
	)

	for _, f := range files {
		wg.Add(1)
		go func(path string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			result := processExample(ctx, client, modelName, path)
			writeResult(result, path)

			n := done.Add(1)
			if result.Error != "" {
				errCount.Add(1)
			}
			if n%10 == 0 || n == total {
				log.Printf("  %d/%d done (%d errors)", n, total, errCount.Load())
			}
		}(f)
	}

	wg.Wait()

	correct := countCorrect()
	log.Printf("\ndone — %d/%d examples, %d errors", total, total, errCount.Load())
	log.Printf("results in %s/", resultsDir)
	log.Printf("event_type accuracy: %d/%d (%.1f%%)", correct.eventType, correct.scored, pct(correct.eventType, correct.scored))
	log.Printf("goroutine_id accuracy: %d/%d (%.1f%%)", correct.goroutineID, correct.scored, pct(correct.goroutineID, correct.scored))
}

// processExample loads one eval example, calls the Gemini API, and returns a scored result.
func processExample(ctx context.Context, client *genai.Client, modelName, path string) evalResult {
	ex, err := loadExample(path)
	if err != nil {
		return evalResult{Error: fmt.Sprintf("load: %v", err)}
	}

	prompt := buildPrompt(ex)

	cfg := &genai.GenerateContentConfig{
		Temperature:     genai.Ptr(float32(0.0)),
		MaxOutputTokens: 512,
		ThinkingConfig:  &genai.ThinkingConfig{ThinkingBudget: genai.Ptr(int32(0))},
	}

	raw, apiErr := callWithRetry(ctx, client, modelName, prompt, cfg)
	if apiErr != nil {
		return evalResult{
			ProgramID:          ex.ProgramID,
			RunIndex:           ex.RunIndex,
			SplitPercent:       ex.SplitPercent,
			FullOutcome:        ex.FullOutcome,
			ConcurrencyPattern: ex.ConcurrencyPattern,
			Nondeterminism:     ex.Nondeterminism,
			IsDeadlockExample:  ex.TimedOut,
			Error:              fmt.Sprintf("api: %v", apiErr),
		}
	}

	pred, parseErr := parseResponse(raw)

	result := evalResult{
		ProgramID:          ex.ProgramID,
		RunIndex:           ex.RunIndex,
		SplitPercent:       ex.SplitPercent,
		FullOutcome:        ex.FullOutcome,
		ConcurrencyPattern: ex.ConcurrencyPattern,
		Nondeterminism:     ex.Nondeterminism,
		IsDeadlockExample:  ex.TimedOut,
		Predicted:          pred,
		RawResponse:        raw,
	}

	if parseErr != nil {
		result.Error = fmt.Sprintf("parse: %v", parseErr)
		return result
	}

	// Deadlock examples have no ground-truth next event — leave scores nil.
	if ex.TimedOut || ex.NextEvent == nil {
		return result
	}

	result.GroundTruthEventType = string(ex.NextEvent.EventType)
	result.GroundTruthGoroutineID = ex.NextEvent.GoroutineID

	if pred != nil {
		correctET := pred.EventType == string(ex.NextEvent.EventType)
		correctGID := pred.GoroutineID == ex.NextEvent.GoroutineID
		result.CorrectEventType = &correctET
		result.CorrectGoroutineID = &correctGID
	}

	return result
}

// callWithRetry calls the Gemini API once, retrying once on error after a 2s pause.
func callWithRetry(ctx context.Context, client *genai.Client, modelName, prompt string, cfg *genai.GenerateContentConfig) (string, error) {
	resp, err := client.Models.GenerateContent(ctx, modelName, genai.Text(prompt), cfg)
	if err != nil {
		time.Sleep(2 * time.Second)
		resp, err = client.Models.GenerateContent(ctx, modelName, genai.Text(prompt), cfg)
		if err != nil {
			return "", err
		}
	}
	return resp.Text(), nil
}

// buildPrompt constructs the zero-shot prompt from an eval example.
func buildPrompt(ex *evalExample) string {
	traceJSON, _ := json.MarshalIndent(ex.PartialTrace, "", "  ")

	currentStateJSON := []byte("{}")
	if len(ex.PartialTrace) > 0 {
		currentStateJSON, _ = json.MarshalIndent(ex.PartialTrace[len(ex.PartialTrace)-1], "", "  ")
	}

	return fmt.Sprintf(`You are reasoning about concurrent Go program execution.

Here is a Go program:
<program>
%s
</program>

Here is a partial execution trace showing goroutine scheduler events so far:
<trace>
%s
</trace>

The current goroutine states are:
<current_state>
%s
</current_state>

Predict the next scheduler event. What happens next?
Respond in JSON only — no markdown fences, no text outside the JSON object:
{"event_type":"GoStart|GoBlock|GoUnblock|GoCreate|GoEnd|GoSched","goroutine_id":<integer>,"reasoning":"<brief explanation>","confidence":"high|medium|low"}`,
		ex.ProgramSource,
		string(traceJSON),
		string(currentStateJSON),
	)
}

// parseResponse strips optional markdown fences and decodes the model's JSON reply.
func parseResponse(raw string) (*predictedEvent, error) {
	text := strings.TrimSpace(raw)
	// Strip ```json ... ``` fences if present.
	if strings.HasPrefix(text, "```") {
		lines := strings.SplitN(text, "\n", 2)
		if len(lines) == 2 {
			text = lines[1]
		}
		text = strings.TrimSuffix(strings.TrimSpace(text), "```")
		text = strings.TrimSpace(text)
	}
	var pred predictedEvent
	if err := json.Unmarshal([]byte(text), &pred); err != nil {
		return nil, fmt.Errorf("unmarshal %q: %w", truncate(text, 120), err)
	}
	return &pred, nil
}

// loadExample reads and decodes one dataset JSON file.
func loadExample(path string) (*evalExample, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var ex evalExample
	if err := json.Unmarshal(data, &ex); err != nil {
		return nil, err
	}
	return &ex, nil
}

// writeResult serialises an evalResult to eval/results/<basename>_result.json.
func writeResult(r evalResult, srcPath string) {
	base := strings.TrimSuffix(filepath.Base(srcPath), ".json")
	outPath := filepath.Join(resultsDir, base+"_result.json")
	data, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		log.Printf("marshal result for %s: %v", srcPath, err)
		return
	}
	if err := os.WriteFile(outPath, data, 0o644); err != nil {
		log.Printf("write result for %s: %v", srcPath, err)
	}
}

// counts holds post-run accuracy tallies read from eval/results/.
type counts struct{ scored, eventType, goroutineID int }

// countCorrect reads all result files and tallies accuracy (called after all goroutines finish).
func countCorrect() counts {
	files, _ := filepath.Glob(filepath.Join(resultsDir, "*_result.json"))
	var c counts
	for _, f := range files {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		var r evalResult
		if err := json.Unmarshal(data, &r); err != nil {
			continue
		}
		if r.CorrectEventType == nil {
			continue // deadlock or error — skip
		}
		c.scored++
		if *r.CorrectEventType {
			c.eventType++
		}
		if *r.CorrectGoroutineID {
			c.goroutineID++
		}
	}
	return c
}

func pct(n, d int) float64 {
	if d == 0 {
		return 0
	}
	return float64(n) / float64(d) * 100
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
