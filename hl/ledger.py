"""Hash-chained ledger of everything the holdout told the proposer.

Each entry is chained to the previous head, so the bit total cannot be edited after the fact
without breaking `verify()`. The total is what the certificate charges for.
"""

from __future__ import annotations

import hashlib
import json


class Ledger:
    def __init__(self, n: int, delta: float):
        self.n, self.delta = n, delta
        self.head = hashlib.sha256(f"ledger/v1/n={n}/delta={delta}".encode()).digest()
        self.entries: list[tuple[float, str, bytes]] = []
        self.bits_in = 0.0

    def append(self, bits: float, verdict) -> None:
        body = json.dumps([bits, verdict], separators=(",", ":"))
        self.head = hashlib.sha256(self.head + body.encode()).digest()
        self.entries.append((bits, body, self.head))
        self.bits_in += bits

    def verify(self) -> bool:
        h = hashlib.sha256(f"ledger/v1/n={self.n}/delta={self.delta}".encode()).digest()
        total = 0.0
        for bits, body, head in self.entries:
            h = hashlib.sha256(h + body.encode()).digest()
            if h != head:
                return False
            total += bits
        return h == self.head and abs(total - self.bits_in) < 1e-9
