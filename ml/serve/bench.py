"""
Latency check for ml-serve: python -m ml.serve.bench [--url http://127.0.0.1:8000] [-n 200]

Sends single-fixture match requests and single shots, then prints p50 / p95 / max in ms.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request


def _post(url: str, payload: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def _measure(url: str, payloads: list[dict], n: int) -> dict[str, float]:
    times = []
    for i in range(n):
        started = time.perf_counter()
        _post(url, payloads[i % len(payloads)])
        times.append((time.perf_counter() - started) * 1000)
    times.sort()
    return {"p50_ms": round(statistics.median(times), 1),
            "p95_ms": round(times[int(len(times) * 0.95) - 1], 1),
            "max_ms": round(times[-1], 1)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("-n", type=int, default=200)
    args = p.parse_args()
    pairs = [("BRA", "ARG", "group"), ("ESP", "FRA", "semi_final"), ("ENG", "GER", "final"), ("USA", "MEX", "group")]
    matches = [{"fixtures": [{"home_team": h, "away_team": a, "match_date": "2026-06-11",
                              "competition_stage": s}]} for h, a, s in pairs]
    shots = [{"distance_m": d, "angle_deg": a} for d, a in ((6, 0), (11, 20), (18, 35), (25, 10))]
    print(json.dumps({
        "predict_match": _measure(f"{args.url}/predict/match", matches, args.n),
        "predict_shot": _measure(f"{args.url}/predict/shot", shots, args.n),
    }, indent=2))


if __name__ == "__main__":
    main()
