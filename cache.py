
import time
import heapq
import threading
from typing import Optional, Dict, Tuple


class CacheEntry:
    __slots__ = ("key", "value", "expire_at", "prev", "next", "size", "version")

    def __init__(self, key: str, value: bytes, ttl_sec: float, version: int):
        self.key = key
        self.value = value
        self.expire_at = (time.time() + ttl_sec) if ttl_sec > 0 else float("inf")
        self.prev: Optional["CacheEntry"] = None
        self.next: Optional["CacheEntry"] = None
        self.size = len(key.encode()) + len(value)
        self.version = version  # increments on each SET for lazy heap invalidation


class LRUCache:
    """
    LRU + TTL, capacity by bytes.
    - map: key -> entry
    - doubly linked list for LRU ordering
    - expiry min-heap of (expire_at, version, key) with lazy deletion
    """
    def __init__(self, capacity_bytes: int = 64 * 1024 * 1024):
        self.capacity_bytes = capacity_bytes
        self.bytes = 0
        self.map: Dict[str, CacheEntry] = {}
        self.head: Optional[CacheEntry] = None  # MRU
        self.tail: Optional[CacheEntry] = None  # LRU

        # stats
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.evictions = 0
        self.expired = 0

        # expiry heap
        self._heap: list[Tuple[float, int, str]] = []
        self._version_counter = 0

        # lock
        self.lock = threading.RLock()

        # background expiry
        self._stop = False
        self._sweeper = threading.Thread(target=self._sweeper_loop, daemon=True)
        self._sweeper.start()

    def close(self):
        self._stop = True

    def _sweeper_loop(self):
        while not self._stop:
            self._sweep_expired_budget(0.01)  # sweep a few items very cheaply
            time.sleep(0.05)

    def _sweep_expired_budget(self, budget_sec: float = 0.01):
        deadline = time.time() + budget_sec
        with self.lock:
            now = time.time()
            while self._heap and time.time() < deadline:
                expire_at, version, key = self._heap[0]
                if expire_at > now:
                    break
                heapq.heappop(self._heap)
                e = self.map.get(key)
                if not e or e.version != version:
                    # stale heap node
                    continue
                if e.expire_at <= now:
                    self._remove_entry(e)
                    self.expired += 1

    def _push_expiry(self, e: CacheEntry):
        if e.expire_at != float("inf"):
            heapq.heappush(self._heap, (e.expire_at, e.version, e.key))

    def _bump_version(self) -> int:
        self._version_counter += 1
        return self._version_counter

    def get(self, key: str) -> Optional[bytes]:
        with self.lock:
            e = self.map.get(key)
            if not e:
                self.misses += 1
                return None
            if e.expire_at <= time.time():
                self._remove_entry(e)
                self.misses += 1
                self.expired += 1
                return None
            self._move_to_head(e)
            self.hits += 1
            return e.value

    def set(self, key: str, value: bytes, ttl_sec: float = 0.0):
        with self.lock:
            e = self.map.get(key)
            if e:
                # update existing
                old_size = e.size
                e.value = value
                e.size = len(key.encode()) + len(value)
                self.bytes += (e.size - old_size)
                e.version = self._bump_version()
                e.expire_at = (time.time() + ttl_sec) if ttl_sec > 0 else float("inf")
                self._move_to_head(e)
                self._push_expiry(e)
            else:
                e = CacheEntry(key, value, ttl_sec, self._bump_version())
                self.map[key] = e
                self._add_to_head(e)
                self.bytes += e.size
                self._push_expiry(e)

            self.sets += 1
            self._evict_if_needed()

    def delete(self, key: str) -> int:
        with self.lock:
            e = self.map.get(key)
            if not e:
                return 0
            self._remove_entry(e)
            return 1

    # --- internal LRU + eviction helpers ---
    def _evict_if_needed(self):
        while self.bytes > self.capacity_bytes and self.tail:
            victim = self.tail
            self._remove_entry(victim)
            self.evictions += 1

    def _remove_entry(self, e: CacheEntry):
        if e.key in self.map:
            del self.map[e.key]
        self.bytes -= e.size
        # unlink
        if e.prev:
            e.prev.next = e.next
        if e.next:
            e.next.prev = e.prev
        if self.head is e:
            self.head = e.next
        if self.tail is e:
            self.tail = e.prev
        e.prev = e.next = None

    def _add_to_head(self, e: CacheEntry):
        e.prev = None
        e.next = self.head
        if self.head:
            self.head.prev = e
        self.head = e
        if self.tail is None:
            self.tail = e

    def _move_to_head(self, e: CacheEntry):
        if self.head is e:
            return
        # unlink
        if e.prev:
            e.prev.next = e.next
        if e.next:
            e.next.prev = e.prev
        if self.tail is e:
            self.tail = e.prev
        # link front
        e.prev = None
        e.next = self.head
        if self.head:
            self.head.prev = e
        self.head = e

    # --- stats ---
    def stats(self):
        with self.lock:
            return {
                "keys": len(self.map),
                "bytes": self.bytes,
                "capacity": self.capacity_bytes,
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "evictions": self.evictions,
                "expired": self.expired,
            }
