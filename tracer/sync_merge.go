package tracer

// liveChan and liveMutex track running channel/mutex state as sync events arrive.
// These types are shared between parser.go (inline trace.Log approach) and
// sync_merge.go (sidecar file approach).

type liveChan struct {
	dataqsiz    int
	qcount      int
	recvWaiters []uint64
	sendWaiters []uint64
}

type liveMutex struct {
	holder  uint64
	waiters []uint64
}

func chanOrNew(chans map[string]*liveChan, id string, dataqsiz int) *liveChan {
	if lc, ok := chans[id]; ok {
		return lc
	}
	lc := &liveChan{dataqsiz: dataqsiz}
	chans[id] = lc
	return lc
}

func mutexOrNew(mutexes map[string]*liveMutex, id string) *liveMutex {
	if lm, ok := mutexes[id]; ok {
		return lm
	}
	lm := &liveMutex{}
	mutexes[id] = lm
	return lm
}

func snapshotChans(chans map[string]*liveChan) map[string]ChanState {
	out := make(map[string]ChanState, len(chans))
	for id, lc := range chans {
		out[id] = ChanState{
			ID:          id,
			DataQSiz:    lc.dataqsiz,
			QCount:      lc.qcount,
			RecvWaiters: cloneUint64(lc.recvWaiters),
			SendWaiters: cloneUint64(lc.sendWaiters),
		}
	}
	return out
}

func snapshotMutexes(mutexes map[string]*liveMutex) map[string]MutexState {
	out := make(map[string]MutexState, len(mutexes))
	for id, lm := range mutexes {
		out[id] = MutexState{
			ID:      id,
			Holder:  lm.holder,
			Waiters: cloneUint64(lm.waiters),
		}
	}
	return out
}

func appendUniq(s []uint64, v uint64) []uint64 {
	for _, x := range s {
		if x == v {
			return s
		}
	}
	return append(s, v)
}

func removeUint64(s []uint64, v uint64) []uint64 {
	for i, x := range s {
		if x == v {
			return append(s[:i], s[i+1:]...)
		}
	}
	return s
}

func cloneUint64(s []uint64) []uint64 {
	if len(s) == 0 {
		return nil
	}
	out := make([]uint64, len(s))
	copy(out, s)
	return out
}
