# app.py
import threading
from flask import Flask, request, jsonify, send_from_directory
import requests, time, json, hashlib, os, random
from dataclasses import dataclass, field
from typing import List, Dict
from threading import Lock
from flask_cors import CORS

import sys
import io

# Force UTF-8 for stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


app = Flask(__name__, static_folder="Front-End")
CORS(app)

# -----------------------------
# Simple blockchain primitives
# -----------------------------
def sha256(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()

DIFFICULTY_PREFIX = "000"

@dataclass
class Tx:
    sender: str
    receiver: str
    amount: int
    nonce: int
    txid: str = ""

    def to_json(self):
        return {"sender": self.sender, "receiver": self.receiver, "amount": int(self.amount), "nonce": int(self.nonce), "txid": self.txid}

    @staticmethod
    def from_json(d: dict):
        return Tx(str(d.get("sender","")), str(d.get("receiver","")), int(d.get("amount",0)), int(d.get("nonce",0)), d.get("txid",""))

    def compute_txid(self):
        self.txid = sha256(f"{self.sender}|{self.receiver}|{self.amount}|{self.nonce}")
        return self.txid

@dataclass
class Block:
    index: int
    prev_hash: str
    timestamp: float
    nonce: int
    txs: List[Tx] = field(default_factory=list)

    def header(self) -> str:
        tx_str = json.dumps([t.to_json() for t in self.txs], sort_keys=True)
        return f"{self.index}|{self.prev_hash}|{self.timestamp}|{self.nonce}|{tx_str}"

    def hash(self) -> str:
        return sha256(self.header())

class Blockchain:
    def __init__(self, alloc: Dict[str, int]):
        self.balances = {a: int(v) for a, v in alloc.items()}
        self.nonces = {a: 0 for a in alloc.keys()}
        genesis = Block(0, "GENESIS", time.time(), 0, [])
        self.chain: List[Block] = [genesis]
        self.mempool: Dict[str, Tx] = {}

    def validate_tx(self, tx: Tx) -> bool:
        if tx.txid == "": tx.compute_txid()
        if tx.sender not in self.balances: return False
        if self.balances[tx.sender] < tx.amount: return False
        if self.nonces.get(tx.sender, 0) != tx.nonce: return False
        for t in self.mempool.values():
            if t.sender == tx.sender and t.nonce == tx.nonce:
                return False
        return True

    def add_tx(self, tx: Tx) -> bool:
        if self.validate_tx(tx):
            self.mempool[tx.txid] = tx
            return True
        return False

    def mine_block(self, miner_addr: str, reward: int = 50) -> Block:
        coinbase = Tx("COINBASE", miner_addr, reward, 0)
        coinbase.compute_txid()
        txs = [coinbase] + list(self.mempool.values())
        b = Block(len(self.chain), self.chain[-1].hash(), time.time(), 0, txs)
        while not b.hash().startswith(DIFFICULTY_PREFIX):
            b.nonce += 1
        self.apply_block(b)
        self.mempool.clear()
        return b

    def apply_block(self, b: Block) -> bool:
        if b.prev_hash != self.chain[-1].hash(): 
            return False
        for tx in b.txs:
            if tx.sender == "COINBASE":
                self.balances[tx.receiver] = self.balances.get(tx.receiver, 0) + tx.amount
            else:
                if not self.validate_tx(tx): 
                    return False
                self.balances[tx.sender] -= tx.amount
                self.balances[tx.receiver] = self.balances.get(tx.receiver, 0) + tx.amount
                self.nonces[tx.sender] += 1
        self.chain.append(b)
        return True

# -----------------------------
# Globals
# -----------------------------
INITIAL_ALLOC = {"alice": 100, "bob": 50, "attacker": 500, "merchant": 100, "miner": 0}
bc_lock = Lock()
bc = Blockchain(INITIAL_ALLOC)
PEERS = set()
EVENT_LOGS: List[str] = []
PARAMS_FILE = "sim_params.json"
LOG_FILE = "logs.txt"
DEFAULT_NETWORK_DELAY_MS = 50

if not os.path.exists(LOG_FILE):
    open(LOG_FILE, "w").close()

# -----------------------------
# Logging helper
# -----------------------------
def add_log(message: str):
    ts = int(time.time())
    log_entry = f"[{ts}] {message}"
    print(log_entry)
    EVENT_LOGS.append(log_entry)
    if len(EVENT_LOGS) > 2000:
        EVENT_LOGS.pop(0)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print("[WARN] Writing to log file failed:", e)

# -----------------------------
# Helpers: serialize, broadcast
# -----------------------------
def serialize_block(b: Block):
    return {"index": b.index, "prev_hash": b.prev_hash, "timestamp": b.timestamp, "nonce": b.nonce, "txs": [t.to_json() for t in b.txs], "hash": b.hash()}

def _do_post(url: str, payload: dict, timeout=3):
    try:
        requests.post(url, json=payload, timeout=timeout)
        add_log(f"[BPOST] POST {url} OK")
    except Exception as e:
        add_log(f"[WARN] POST {url} failed: {e}")

def broadcast_to_peers(path: str, payload: dict, base_delay_ms: int = None):
    params = load_params()
    base = base_delay_ms if base_delay_ms is not None else int(params.get("NETWORK_DELAY_MS", params.get("ATTACKER_NETWORK_DELAY_MS", DEFAULT_NETWORK_DELAY_MS)))
    for p in list(PEERS):
        jitter = (random.random() * 0.4 - 0.2)
        delay_ms = max(0, int(base * (1.0 + jitter)))
        url = p.rstrip("/") + path
        add_log(f"[BCAST] schedule {url} in {delay_ms} ms")
        threading.Timer(delay_ms / 1000.0, _do_post, args=(url, payload)).start()

def save_params(params: dict):
    try:
        with open(PARAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2)
        return True
    except Exception as e:
        add_log(f"[WARN] Could not save params: {e}")
        return False

def load_params():
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# -----------------------------
# Peer routes
# -----------------------------
@app.route("/add_peer", methods=["POST"])
def add_peer():
    data = request.json
    peer = data.get("peer")
    if peer and peer not in PEERS:
        PEERS.add(peer)
        add_log(f"Peer added: {peer}")
    return jsonify({"peers": list(PEERS)})

@app.route("/peers", methods=["GET"])
def peers():
    return jsonify({"peers": list(PEERS)})

# -----------------------------
# Core API routes
# -----------------------------
@app.route("/api/chain", methods=["GET"])
def api_chain():
    with bc_lock:
        return jsonify([serialize_block(b) for b in bc.chain])

@app.route("/api/balance/<addr>", methods=["GET"])
def api_balance(addr):
    with bc_lock:
        return jsonify({"balance": bc.balances.get(addr, 0), "nonce": bc.nonces.get(addr, 0)})

@app.route("/api/mempool", methods=["GET"])
def api_mempool():
    with bc_lock:
        txs = [t.to_json() for t in bc.mempool.values()]
    return jsonify(txs)

# -----------------------------
# Transaction endpoint (handles attack hijack if armed)
# -----------------------------
@app.route("/api/tx", methods=["POST"])
def api_tx():
    data = request.json
    tx = Tx.from_json(data)
    tx.compute_txid()
    params = load_params()
    with bc_lock:
        mined_block = None
        if params.get("attack_armed", False):
            # disarm and attempt double-spend
            params["attack_armed"] = False
            params["attack_triggered"] = True
            params["target_txid"] = tx.txid
            save_params(params)
            add_log(f"[ATTACK-ARMED] Attack attempt on tx {tx.txid} ({tx.sender} → {tx.receiver}, {tx.amount}). Share={params.get('ATTACKER_HASH_POWER_SHARE', 'N/A')}")
            # attacker crafts a competing tx (double-spend)
            attacker_nonce = bc.nonces.get("attacker", 0)
            attacker_tx = Tx("attacker", "merchant", tx.amount, attacker_nonce)
            attacker_tx.compute_txid()
            bc.add_tx(attacker_tx)
            # probabilistic attacker success sim: if attacker hashshare > random -> attacker mines first
            share = float(params.get("ATTACKER_HASH_POWER_SHARE", 0.5))
            r = random.random()
            if r < share:
                mined_block = bc.mine_block("attacker")
                add_log(f"[ATTACK-SUCCESS] Attacker mined block {mined_block.index} with double-spend {attacker_tx.txid}")
                broadcast_to_peers("/block_gossip", serialize_block(mined_block))
                return jsonify({"accepted": True, "attacked": True, "result": "attacker_mined", "mined_block": serialize_block(mined_block)})
            else:
                # attacker lost — honest miner mines block with the original tx included
                # apply normal flow: add original tx and honest miner mines
                if bc.add_tx(tx):
                    mined_block = bc.mine_block("miner")
                    add_log(f"[ATTACK-FAIL] Attacker lost. Transaction {tx.txid} accepted.")
                    broadcast_to_peers("/block_gossip", serialize_block(mined_block))
                    return jsonify({"accepted": True, "attacked": True, "result": "attacker_lost", "mined_block": serialize_block(mined_block)})
                else:
                    add_log(f"[ATTACK-FAIL] Attacker lost; but tx rejected locally.")
                    return jsonify({"accepted": False, "attacked": True, "result": "attacker_lost_tx_rejected"})
        # Normal flow
        ok = bc.add_tx(tx)
        if ok:
            add_log(f"Transaction {tx.txid} accepted from {tx.sender} → {tx.receiver} ({tx.amount})")
            mined_block = bc.mine_block("miner")
            add_log(f"Block {mined_block.index} mined with {len(mined_block.txs)} tx(s)")
            broadcast_to_peers("/block_gossip", serialize_block(mined_block))
        else:
            add_log(f"Transaction {tx.txid} rejected")
    return jsonify({"accepted": ok, "attacked": False, "txid": tx.txid, "mined_block": serialize_block(mined_block) if mined_block else None})

# gossip endpoints
@app.route("/tx_gossip", methods=["POST"])
def tx_gossip():
    data = request.json
    tx = Tx.from_json(data)
    tx.compute_txid()
    with bc_lock:
        if bc.add_tx(tx):
            add_log(f"Received gossiped transaction {tx.txid}")
    return jsonify({"received": True})

@app.route("/api/mine", methods=["POST"])
def api_mine():
    data = request.json
    miner = data.get("miner", "miner")
    with bc_lock:
        b = bc.mine_block(miner)
        add_log(f"Miner {miner} mined Block {b.index} with {len(b.txs)} tx(s)")
    block_json = serialize_block(b)
    broadcast_to_peers("/block_gossip", block_json)
    return jsonify({"block": block_json})

@app.route("/block_gossip", methods=["POST"])
def block_gossip():
    data = request.json
    txs = [Tx.from_json(t) for t in data.get("txs",[])]
    b = Block(data.get("index",0), data.get("prev_hash",""), data.get("timestamp",time.time()), data.get("nonce",0), txs)
    with bc_lock:
        if bc.apply_block(b):
            add_log(f"Received and applied block {b.index} from gossip")
    return jsonify({"received": True})

# -----------------------------
# Logs + params + run_attack
# -----------------------------
@app.route("/logs", methods=["GET"])
def get_logs():
    return jsonify(EVENT_LOGS[-400:])

@app.route("/set_params", methods=["POST"])
def set_params():
    params = request.json or {}
    ok = save_params(params)
    add_log(f"Attack parameters updated: {params}")
    return jsonify({"status": "params_set" if ok else "error", "params": params})

@app.route("/get_params", methods=["GET"])
def get_params():
    params = load_params()
    return jsonify({"params": params})

@app.route("/run_attack", methods=["POST"])
def run_attack():
    data = request.json or {}
    params = load_params()
    params["attack_armed"] = True
    params["trigger_info"] = data
    save_params(params)
    add_log(f"Run-attack armed from dashboard: {data}")
    return jsonify({"status": "attack_armed", "params": params})

# -----------------------------
# SimBlock ingest
# -----------------------------
@app.route("/simblock_ingest", methods=["POST"])
def simblock_ingest():
    event = request.get_json(force=True, silent=True)
    if not event:
        raw = request.data.decode("utf-8", errors="ignore")
        try:
            event = json.loads(raw)
        except Exception:
            add_log("[SIMBLOCK] Received unparseable payload")
            return jsonify({"status": "error", "message": "unparseable payload"}), 400

    kind = event.get("kind","").lower()
    content = event.get("content",{}) or {}
    params = load_params()
    base_delay = int(params.get("NETWORK_DELAY_MS", params.get("ATTACKER_NETWORK_DELAY_MS", DEFAULT_NETWORK_DELAY_MS)))

    if kind == "add-tx":
        txid = content.get("tx-id") or content.get("txid") or content.get("id") or ""
        sender = content.get("sender") or content.get("from") or ""
        receiver = content.get("receiver") or content.get("to") or ""
        amount = content.get("amount") or content.get("value") or 0
        nonce = content.get("nonce") if content.get("nonce") is not None else 0
        tx_payload = {"sender": str(sender), "receiver": str(receiver), "amount": int(amount), "nonce": int(nonce)}
        add_log(f"[SIMBLOCK] Ingest add-tx: {txid} {sender} → {receiver} ({amount})")
        try:
            _do_post(f"http://127.0.0.1:{PORT}/api/tx", tx_payload)
        except Exception:
            try:
                with bc_lock:
                    tx = Tx.from_json(tx_payload)
                    tx.compute_txid()
                    if bc.add_tx(tx):
                        add_log(f"[SIMBLOCK-APPLY] Local node accepted tx {tx.txid}")
            except Exception as e:
                add_log(f"[SIMBLOCK-APPLY] Local apply failed: {e}")
        broadcast_to_peers("/api/tx", tx_payload, base_delay_ms=base_delay)
        return jsonify({"status":"ok"})
    elif kind == "add-block":
        add_log(f"[SIMBLOCK] Ingest add-block: {content}")
        block_payload = content.copy()
        try:
            _do_post(f"http://127.0.0.1:{PORT}/block_gossip", block_payload)
        except Exception:
            try:
                txs = [Tx.from_json(t) for t in block_payload.get("txs",[])]
                b = Block(block_payload.get("index",0), block_payload.get("prev_hash",""), block_payload.get("timestamp",time.time()), block_payload.get("nonce",0), txs)
                with bc_lock:
                    if bc.apply_block(b):
                        add_log(f"[SIMBLOCK-APPLY] Local applied block {b.index}")
            except Exception as e:
                add_log(f"[SIMBLOCK-APPLY] Local block apply failed: {e}")
        broadcast_to_peers("/block_gossip", block_payload, base_delay_ms=base_delay)
        return jsonify({"status":"ok"})
    elif kind in ("attack-log","attack_log"):
        msg = content.get("message") or content.get("msg") or str(content)
        add_log(f"[ATTACK-LOG] {msg}")
        broadcast_to_peers("/logs", {"forwarded_attack_log": msg}, base_delay_ms=base_delay)
        return jsonify({"status":"ok"})
    else:
        add_log(f"[SIMBLOCK] Unknown ingest: {event}")
        return jsonify({"status":"ok","received":event})

# -----------------------------
# Auto-miner
# -----------------------------
def auto_miner():
    while True:
        time.sleep(5)
        with bc_lock:
            if len(bc.mempool) > 0:
                add_log("[AUTO-MINER] Pending tx found. Mining a new block...")
                mined_block = bc.mine_block("miner")
                broadcast_to_peers("/block_gossip", serialize_block(mined_block))

# -----------------------------
# Serve UI index
# -----------------------------
@app.route("/")
def index():
    return send_from_directory("Front-End", "log.html")

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5001))
    threading.Thread(target=auto_miner, daemon=True).start()
    add_log(f"Starting Flask node on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
