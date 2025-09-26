import time, json, hashlib
from dataclasses import dataclass, field
from typing import List, Dict

def sha256(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()

# Adjust difficulty here (more zeros = slower mining)
DIFFICULTY_PREFIX = "000"

@dataclass
class Tx:
    sender: str
    receiver: str
    amount: int
    nonce: int
    txid: str = ""

    def to_json(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": int(self.amount),
            "nonce": int(self.nonce),
            "txid": self.txid
        }

    @staticmethod
    def from_json(d: Dict):
        return Tx(d["sender"], d["receiver"], int(d["amount"]), int(d["nonce"]), d.get("txid",""))

    def compute_txid(self):
        body = f"{self.sender}|{self.receiver}|{self.amount}|{self.nonce}"
        self.txid = sha256(body)
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
        self.balances: Dict[str, int] = {a:int(v) for a,v in alloc.items()}
        self.nonces: Dict[str, int] = {a:0 for a in alloc.keys()}
        genesis = Block(index=0, prev_hash="GENESIS", timestamp=time.time(), nonce=0, txs=[])
        self.chain: List[Block] = [genesis]
        self.mempool: Dict[str, Tx] = {}

    # ---------- Transactions ----------
    def validate_tx(self, tx: Tx) -> bool:
        if tx.txid == "":
            tx.compute_txid()
        s = tx.sender
        if s not in self.balances: return False
        if self.balances[s] < tx.amount: return False
        if self.nonces.get(s, 0) != tx.nonce: return False
        # prevent duplicate (sender,nonce) tx in mempool
        for t in self.mempool.values():
            if t.sender == s and t.nonce == tx.nonce:
                return False
        return True

    def add_tx(self, tx: Tx) -> bool:
        if self.validate_tx(tx):
            self.mempool[tx.txid] = tx
            return True
        return False

    # ---------- Mining ----------
    def mine_block(self, miner_addr: str, reward: int = 50) -> Block:
        coinbase = Tx(sender="COINBASE", receiver=miner_addr, amount=reward, nonce=0)
        coinbase.compute_txid()
        txs = [coinbase] + list(self.mempool.values())
        b = Block(
            index=len(self.chain),
            prev_hash=self.chain[-1].hash(),
            timestamp=time.time(),
            nonce=0,
            txs=txs
        )
        while not b.hash().startswith(DIFFICULTY_PREFIX):
            b.nonce += 1
        self.apply_block(b)
        self.mempool.clear()
        return b

    def apply_block(self, b: Block) -> bool:
        if b.prev_hash != self.chain[-1].hash(): return False
        for tx in b.txs:
            if tx.sender == "COINBASE":
                self.balances[tx.receiver] = self.balances.get(tx.receiver, 0) + tx.amount
                continue
            if not self.validate_tx(tx): return False
            self.balances[tx.sender] -= tx.amount
            self.balances[tx.receiver] = self.balances.get(tx.receiver, 0) + tx.amount
            self.nonces[tx.sender] = self.nonces.get(tx.sender, 0) + 1
        self.chain.append(b)
        return True
