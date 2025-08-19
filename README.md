# Zencastr Cache (Python)

A fast in-memory cache service with LRU eviction, TTL expiration, and a simple text TCP protocol (inspired by Redis/Memcached).

## Features
- **LRU eviction** by byte capacity (O(1) ops via doubly-linked list).
- **TTL expiration** with a min-heap and lazy deletion (no O(n) sweeps).
- **Thread-safe** core with a re-entrant lock.
- **Zero-copy-ish** value path (values are `bytes`, binary-safe protocol).
- **Simple TCP protocol**: `SET`, `GET`, `DEL`, `STATS`.
- Runnable standalone server, client, and a tiny benchmark.

## Protocol

Line-oriented ASCII commands; values are raw bytes and binary-safe.

```
SET <key> <ttl_ms> <nbytes>\n<raw-bytes>\n   -> OK\n or ERR <msg>\n
GET <key>\n                                 -> VALUE <nbytes>\n<raw-bytes>\n  or NOT_FOUND\n
DEL <key>\n                                 -> DELETED <n>\n
STATS\n                                     -> STATS {json}\n
```

**Notes**
- `ttl_ms=0` means no expiration.
- After `SET` metadata line, the server reads exactly `<nbytes>` followed by a single trailing `\n`.

## Run

Requires **Python 3.10+** (uses typing features and per-connection threads). No third-party dependencies.

```bash
python server.py --host 0.0.0.0 --port 9000 --capacity-mb 64
```

## Try it

In another terminal:

```bash
python client.py
```

Or use `nc`:

```bash
printf "SET foo 5000 3\nbar\n" | nc 127.0.0.1 9000
printf "GET foo\n" | nc 127.0.0.1 9000
printf "STATS\n" | nc 127.0.0.1 9000
```

## Benchmark 

```bash
python bench.py --n 20000
```

## Design Notes
- **LRU**: explicit doubly-linked list with hash map for O(1) insert/move/evict.
- **TTL**: `heapq` min-heap of `(expire_at, version, key)` tuples. On update, a new tuple is pushed; old entries are discarded when popped ("lazy"). No O(n) scan threads.
- **Concurrency**: each client connection handled by a daemon thread; core cache uses a single `RLock` for simplicity and correctness.
- **Memory accounting**: bytes = `len(key) + len(value)`; eviction runs until within capacity.
- **Robust protocol parsing**: state machine that never `recv()`s inside command handler; it buffers and only advances when enough bytes are present.

