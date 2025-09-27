import time
from scripts.component_stage3_analyze import stage3_analyze, stage3_analyze_threaded


class SlowFakeLLM:
    def __init__(self, delay=0.05):
        self.delay = delay

    def attention_decision(self, item):
        time.sleep(self.delay)
        return {
            "attention_needed": True,
            "severity": "watch",
            "reasons": [f"Processed {item.get('ticker')}"],
            "email": {"subject": f"Subj {item.get('ticker')}", "body": "Body"},
        }


def test_stage3_threaded_speedup():
    enriched = {"items": [{"ticker": f"T{i}"} for i in range(8)]}
    # Sequential time
    t0 = time.time()
    seq = stage3_analyze(enriched, SlowFakeLLM(delay=0.1))
    t1 = time.time()
    # Threaded time (4 workers)
    def factory():
        return SlowFakeLLM(delay=0.1)

    t2 = time.time()
    thr = stage3_analyze_threaded(enriched, workers=4, llm_factory=factory)
    t3 = time.time()

    seq_elapsed = t1 - t0
    thr_elapsed = t3 - t2
    # Expect notable speedup
    assert thr_elapsed < seq_elapsed * 0.7
    # Output shape matches
    assert len(seq["items"]) == len(thr["items"]) == 8
    assert len(thr["alerts"]) == 8

