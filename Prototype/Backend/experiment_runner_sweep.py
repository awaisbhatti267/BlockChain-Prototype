# experiment_runner_sweep.py
import subprocess, time, os, csv, itertools, json
from experiment_runner import run_trials

# Sweep settings
shares = [0.1, 0.25, 0.5, 0.75, 0.9]
delays = [20, 50, 200]
trials_per_combo = 10

summary = []
for share, delay in itertools.product(shares, delays):
    print(f"Running combo share={share}, delay={delay}")
    results = run_trials(trials=trials_per_combo, attacker_share=share, delay_ms=delay)
    succ = sum(1 for r in results if r["outcome"]=="success")
    fail = sum(1 for r in results if r["outcome"]=="fail")
    timeout = sum(1 for r in results if r["outcome"] not in ("success","fail"))
    summary.append({"share": share, "delay": delay, "trials": trials_per_combo, "successes": succ, "fails": fail, "timeouts": timeout})

# write summary CSV
with open("sweep_summary.csv","w", newline="", encoding="utf-8") as f:
    import csv
    w = csv.DictWriter(f, fieldnames=["share","delay","trials","successes","fails","timeouts"])
    w.writeheader()
    for row in summary:
        w.writerow(row)
print("Sweep complete. Summary saved to sweep_summary.csv")
