# parse_simblock_tx_logs.py
# Enhanced parser for SimBlock output
# Generates tx_summary.csv and block_summary.csv with realistic txids and attacker tagging

import sys, os, glob, json, csv, hashlib

def fake_hash(s: str) -> str:
    """Generate a fake txid using SHA256 so it looks realistic."""
    return hashlib.sha256(s.encode()).hexdigest()[:64]

def find_jsons(root):
    root = os.path.abspath(root)
    if os.path.isfile(root) and root.lower().endswith(".json"):
        return [root]
    pattern = os.path.join(root, "**", "*.json")
    files = glob.glob(pattern, recursive=True)
    extra = [
        os.path.join(root, "simulator", "src", "dist", "output", "*.json"),
        os.path.join(root, "simulator", "src", "dist", "output", "output.json"),
        os.path.join(root, "simulator", "src", "dist", "output", "static.json"),
    ]
    for p in extra:
        files.extend(glob.glob(p, recursive=True))
    files = sorted(set(files))
    return [f for f in files if os.path.isfile(f)]

def walk_json(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_json(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_json(item)

def is_tx_candidate(d):
    if not isinstance(d, dict): return False
    keys = {k.lower() for k in d.keys()}
    if "txid" in keys or ("sender" in keys and "receiver" in keys) or ("from" in keys and "to" in keys) or "amount" in keys:
        return True
    return False

def is_block_candidate(d):
    if not isinstance(d, dict): return False
    keys = {k.lower() for k in d.keys()}
    if "block" in keys or "block_id" in keys or "hash" in keys or "height" in keys:
        return True
    if "txs" in keys or "transactions" in keys:
        return True
    return False

def extract_tx_from_dict(d, idx, fname):
    def g(*names):
        for n in names:
            for k in d:
                if k.lower() == n.lower():
                    return d[k]
        return ""
    sender = g("sender","from","src")
    receiver = g("receiver","to","dst")
    amount = g("amount","value")
    timev = g("time","timestamp")
    # build fake txid
    raw = f"{sender}-{receiver}-{amount}-{timev}-{idx}-{fname}"
    txid = fake_hash(raw)
    attacker_flag = "YES" if "attacker" in str(sender).lower() else "NO"
    return {
        "txid": txid,
        "from": str(sender),
        "to": str(receiver),
        "amount": str(amount),
        "time": str(timev or 0),
        "attacker": attacker_flag
    }

def extract_block_from_dict(d):
    def g(*names):
        for n in names:
            for k in d:
                if k.lower() == n.lower():
                    return d[k]
        return ""
    block_id = g("block","block_id","hash","id")
    height = g("height","index")
    txs = g("txs","transactions")
    tx_count = ""
    if isinstance(txs, list):
        tx_count = len(txs)
    return {
        "block_id": str(block_id),
        "height": str(height),
        "txs_count": str(tx_count)
    }

def parse_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception:
            return [], []
    txs, blocks = [], []
    for node in walk_json(data):
        if is_tx_candidate(node):
            txs.append(node)
        if is_block_candidate(node):
            blocks.append(node)
    return txs, blocks

def main():
    root = "."
    if len(sys.argv) > 1:
        root = sys.argv[1]
    files = find_jsons(root)
    if not files:
        print("No JSON files found. Provide the folder/file path as argument.")
        return

    print(f"[INFO] Parsing {len(files)} file(s)")
    tx_rows, block_rows = [], []
    for p in files:
        print(f"  - scanning {p}")
        try:
            txs, blocks = parse_file(p)
        except Exception as e:
            print(f"    [WARN] failed to parse {p}: {e}")
            continue
        for idx, d in enumerate(txs):
            extracted = extract_tx_from_dict(d, idx, os.path.basename(p))
            tx_rows.append({
                "file": os.path.basename(p),
                "line_no": idx,
                **extracted
            })
        for idx, d in enumerate(blocks):
            b = extract_block_from_dict(d)
            block_rows.append({
                "file": os.path.basename(p),
                "line_no": idx,
                "time": "",
                **b
            })

    # write CSVs
    if tx_rows:
        with open("tx_summary.csv","w",newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["file","line_no","time","txid","from","to","amount","attacker"])
            writer.writeheader()
            writer.writerows(tx_rows)
        print(f"[OK] tx_summary.csv ({len(tx_rows)} rows)")
    else:
        print("[INFO] no transactions detected")

    if block_rows:
        with open("block_summary.csv","w",newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["file","line_no","time","block_id","height","txs_count"])
            writer.writeheader()
            writer.writerows(block_rows)
        print(f"[OK] block_summary.csv ({len(block_rows)} rows)")
    else:
        print("[INFO] no blocks detected")

if __name__ == "__main__":
    main()
