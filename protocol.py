
import json
from typing import Optional
from cache import LRUCache


class ProtocolHandler:
    """
    Incremental parser; does not call recv() itself. You feed raw bytes via on_data().
    Protocol:
      SET <key> <ttl_ms> <nbytes>\n<payload><\n>
      GET <key>\n
      DEL <key>\n
      STATS\n
    """
    def __init__(self, cache: LRUCache, send_func):
        self.cache = cache
        self.send = send_func
        self.buf = bytearray()
        self.state = "READ_LINE"
        self._pending = None  # type: Optional[dict]

    def on_data(self, data: bytes):
        self.buf.extend(data)
        while True:
            if self.state == "READ_LINE":
                nl = self._find_newline()
                if nl < 0:
                    return
                line = self._consume(nl).decode("utf-8", errors="replace").strip()
                self._consume(1)  # the '\n'
                if not line:
                    continue
                self._handle_line(line)

            elif self.state == "READ_VALUE":
                need = self._pending["nbytes"] + 1  # payload + trailing '\n'
                if len(self.buf) < need:
                    return
                value = self._consume(self._pending["nbytes"])
                trailing = self._consume(1)
                if trailing != b"\n":
                    self.send(b"ERR protocol: missing newline after payload\n")
                    self.state = "READ_LINE"
                    self._pending = None
                    continue
                # apply SET
                ttl_ms = self._pending["ttl_ms"]
                key = self._pending["key"]
                self.cache.set(key, bytes(value), ttl_ms / 1000.0)
                self.send(b"OK\n")
                self.state = "READ_LINE"
                self._pending = None

            else:
                # reset if unknown
                self.state = "READ_LINE"

    def _handle_line(self, line: str):
        parts = line.split()
        cmd = parts[0].upper()

        if cmd == "SET" and len(parts) == 4:
            key = parts[1]
            try:
                ttl_ms = int(parts[2])
                nbytes = int(parts[3])
                if nbytes < 0:
                    raise ValueError
            except ValueError:
                self.send(b"ERR invalid SET args\n"); return
            self._pending = {"key": key, "ttl_ms": ttl_ms, "nbytes": nbytes}
            self.state = "READ_VALUE"
            return

        if cmd == "GET" and len(parts) == 2:
            val = self.cache.get(parts[1])
            if val is None:
                self.send(b"NOT_FOUND\n")
            else:
                self.send(f"VALUE {len(val)}\n".encode() + val + b"\n")
            return

        if cmd == "DEL" and len(parts) == 2:
            n = self.cache.delete(parts[1])
            self.send(f"DELETED {n}\n".encode())
            return

        if cmd == "STATS" and len(parts) == 1:
            s = json.dumps(self.cache.stats(), separators=(",", ":"))
            self.send(f"STATS {s}\n".encode())
            return

        self.send(b"ERR unknown or invalid command\n")

    # --- buffer helpers ---
    def _find_newline(self) -> int:
        try:
            return self.buf.index(0x0A)  # '\n'
        except ValueError:
            return -1

    def _consume(self, n: int) -> bytes:
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out
