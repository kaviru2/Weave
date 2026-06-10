// WEAVE_META
// outcome: leak
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel etcd_6708 (leak)

package main

import (
	"os"
	"runtime/trace"
	"context"
	"sync"
	)

type EndpointSelectionMode int

const (
	EndpointSelectionRandom EndpointSelectionMode = iota
	EndpointSelectionPrioritizeLeader
)

type MembersAPI interface {
	Leader(ctx context.Context)
}

type Client interface {
	Sync(ctx context.Context)
	SetEndpoints()
	httpClient
}

type httpClient interface {
	Do(context.Context)
}

type httpClusterClient struct {
	sync.RWMutex
	selectionMode EndpointSelectionMode
}

func (c *httpClusterClient) getLeaderEndpoint() {
	mAPI := NewMembersAPI(c)
	mAPI.Leader(context.Background())
}

func (c *httpClusterClient) SetEndpoints() {
	switch c.selectionMode {
	case EndpointSelectionRandom:
	case EndpointSelectionPrioritizeLeader:
		c.getLeaderEndpoint()
	}
}

func (c *httpClusterClient) Do(ctx context.Context) {
	c.RLock() // block here
	c.RUnlock()
}

func (c *httpClusterClient) Sync(ctx context.Context) {
	c.Lock()
	defer c.Unlock()

	c.SetEndpoints()
}

type httpMembersAPI struct {
	client httpClient
}

func (m *httpMembersAPI) Leader(ctx context.Context) {
	m.client.Do(ctx)
}

func NewMembersAPI(c Client) MembersAPI {
	return &httpMembersAPI{
		client: c,
	}
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

	hc := &httpClusterClient{
		selectionMode: EndpointSelectionPrioritizeLeader,
	}
	hc.Sync(context.Background())
}
