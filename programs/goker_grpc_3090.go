// WEAVE_META
// outcome: race
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel grpc_3090 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
		"time"
)

type resolver_ClientConn interface {
	UpdateState()
}

type resolver_Resolver struct {
	CC resolver_ClientConn
}

func (r *resolver_Resolver) Build(cc resolver_ClientConn) Resolver {
	r.CC = cc
	r.UpdateState()
	return r
}

func (r *resolver_Resolver) ResolveNow() {
}

func (r *resolver_Resolver) UpdateState() {
	r.CC.UpdateState()
}

type Resolver interface {
	ResolveNow()
}

type ccResolverWrapper struct {
	cc       *ClientConn
	resolver Resolver
	mu       sync.Mutex
}

func (ccr *ccResolverWrapper) resolveNow() {
	ccr.mu.Lock()
	ccr.resolver.ResolveNow()
	ccr.mu.Unlock()
}

func (ccr *ccResolverWrapper) poll() {
	ccr.mu.Lock()
	defer ccr.mu.Unlock()
	go func() {
		ccr.resolveNow()
	}()
}

func (ccr *ccResolverWrapper) UpdateState() {
	ccr.poll()
}

func newCCResolverWrapper(cc *ClientConn) {
	rb := cc.dopts.resolverBuilder
	ccr := &ccResolverWrapper{}
	ccr.resolver = rb.Build(ccr)
}

type Builder interface {
	Build(cc resolver_ClientConn) Resolver
}

type dialOptions struct {
	resolverBuilder Builder
}

type ClientConn struct {
	dopts dialOptions
}

func DialContext() {
	cc := &ClientConn{
		dopts: dialOptions{},
	}
	if cc.dopts.resolverBuilder == nil {
		cc.dopts.resolverBuilder = &resolver_Resolver{}
	}
	newCCResolverWrapper(cc)
}
func Dial() {
	DialContext()
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

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		Dial()
		time.Sleep(5 * time.Millisecond)
	}()
	wg.Wait()
}
