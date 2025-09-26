# experiment_runner.py
import requests, time, csv, sys, os, random

# configure node to drive (primary)
PRIMARY = "http://127.0.0.1:5001"
LOGS = PRIMARY + "/logs"
SET_PARAMS = PRIMARY + "/set_params"
RUN_ATTACK = PRIMARY + "/run_attack"
API_TX = PRIMARY + "/api/tx"
GET_PARAMS = PRIMARY + "/get_params"

def set_params(params):
    r = requests.post(SET_PARAMS, json=params, timeout=5)
    return r.json()

def arm_attack():
    r = requests.post(RUN_ATTACK, json={"requested_by":"experiment","ts":time.time()}, timeout=5)
    return r.json()

def send_tx(sender, receiver, amount, nonce=0):
    payload = {"sender": sender, "receiver": receiver, "amount": amount, "nonce": nonce}
    r = requests.post(API_TX, json=payload, timeout=10)
    return r.json()

def fetch_logs():
    r = requests.get(LOGS, timeout=5)
    return r.json()

def find_outcome(logs, target_txid=None, since_ts=None):
    # look for ATTACK-SUCCESS or ATTACK-FAIL or ATTACK-SUCCESS lines
    for line in reversed(logs):
        if "ATTACK-SUCCESS" in line:
            return "success", line
        if "ATTACK-FAIL" in line:
            return "fail", line
    return "unknown", ""

def run_trials(trials=20, attacker_share=0.5, delay_ms=50, confirmations=1):
    # set params for this experiment
    params = {
        "ATTACKER_HASH_POWER_SHARE": attacker_share,
        "ATTACKER_NETWORK_DELAY_MS": delay_ms,
        "VICTIM_CONFIRMATIONS": confirmations,
        "NUM_OF_NODES": 3
    }
    set_params(params)
    print("Params set:", params)

    results = []
    for t in range(trials):
        print(f"Trial {t+1}/{trials}")
        # arm attack
        arm_attack()
        time.sleep(0.2)
        # create a transaction from alice->bob with nonce from node
        # fetch alice nonce
        try:
            r = requests.get(PRIMARY + "/api/balance/alice", timeout=3).json()
            nonce = r.get("nonce",0)
        except Exception:
            nonce = 0
        txres = send_tx("alice","bob",10, nonce)
        txid = txres.get("txid", "")
        # wait for outcome in logs (timeout)
        outcome="timeout"
        info=""
        deadline = time.time()+8
        while time.time() < deadline:
            logs = fetch_logs()
            outcome, info = find_outcome(logs, target_txid=txid)
            if outcome != "unknown":
                break
            time.sleep(0.5)
        print("Outcome:", outcome, info)
        results.append({"trial": t+1, "attacker_share": attacker_share, "delay_ms": delay_ms, "outcome": outcome, "info": info, "txid": txid})
        # small cool-down
        time.sleep(0.5)

    # write csv
    fn = f"results_share_{attacker_share}_delay_{delay_ms}.csv"
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["trial","attacker_share","delay_ms","outcome","info","txid"])
        w.writeheader()
        for r in results:
            w.writerow(r)
    print("Wrote", fn)
    return results

if __name__ == "__main__":
    trials = int(sys.argv[1]) if len(sys.argv)>1 else 20
    share = float(sys.argv[2]) if len(sys.argv)>2 else 0.5
    delay = int(sys.argv[3]) if len(sys.argv)>3 else 50
    run_trials(trials=trials, attacker_share=share, delay_ms=delay)
