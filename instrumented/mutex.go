package instrumented

import "sync"

// WeaveMutex is an instrumented mutex wrapper. It behaves exactly like sync.Mutex
// but emits trace.Log events recording the holder goroutine ID on every lock/unlock.
type WeaveMutex struct {
	id string
	mu sync.Mutex
}

// NewMutex creates an instrumented mutex.
func NewMutex() *WeaveMutex {
	id := newID("mx")
	emit(SyncPayload{Kind: "mutex_create", MutexID: id, GoID: curGoid()})
	return &WeaveMutex{id: id}
}

// Lock acquires the mutex. Emits mutex_lock_start before blocking and mutex_lock_done
// with the holder goroutine ID after the lock is acquired.
func (wm *WeaveMutex) Lock() {
	gid := curGoid()
	emit(SyncPayload{Kind: "mutex_lock_start", MutexID: wm.id, GoID: gid})
	wm.mu.Lock()
	emit(SyncPayload{Kind: "mutex_lock_done", MutexID: wm.id, GoID: gid, Holder: gid})
}

// Unlock releases the mutex and emits a mutex_unlock event.
func (wm *WeaveMutex) Unlock() {
	gid := curGoid()
	emit(SyncPayload{Kind: "mutex_unlock", MutexID: wm.id, GoID: gid, Holder: 0})
	wm.mu.Unlock()
}
