// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: channel
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel kubernetes_82550 (nonblocking)

package main

import (

	"os"
	"runtime/trace"
)

type DockerConfig map[string]DockerConfigEntry

type DockerConfigEntry struct{}

type CachingDockerConfigProvider struct {
	cacheDockerConfig DockerConfig
}

func (d *CachingDockerConfigProvider) Provide() DockerConfig {
	return DockerConfig{}
}

type lazyEcrProvider struct {
	actualProvider *CachingDockerConfigProvider
}

func (p *lazyEcrProvider) LazyProvide() *DockerConfigEntry {
	if p.actualProvider == nil {
		p.actualProvider = &CachingDockerConfigProvider{}
	}
	entry := p.actualProvider.Provide()["0"]
	return &entry
}

func main() {
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
		f, err := os.Create(tf)
		if err == nil {
			if err := trace.Start(f); err == nil {
				defer func() { trace.Stop(); f.Close() }()
			}
		}
	}

	provider := &lazyEcrProvider{}
	for i := 0; i < 10; i++ {
		go provider.LazyProvide()
	}
}
