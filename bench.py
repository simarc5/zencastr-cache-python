
import argparse
import socket
import time
import threading


def bench_set(n: int, host="127.0.0.1", port=9000):
    s = socket.create_connection((host, port))
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    start = time.time()
    for i in range(n):
        payload = b"value\n"
        s.sendall(f"SET k{i} 0 {len(payload)-1}\n".encode() + payload)
        s.recv(16)  # "OK\n"
    elapsed = time.time() - start
    s.close()
    return n / elapsed, elapsed


def bench_get(n: int, host="127.0.0.1", port=9000):
    s = socket.create_connection((host, port))
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    start = time.time()
    for i in range(n):
        s.sendall(f"GET k{i}\n".encode())
        s.recv(64)  # small values
    elapsed = time.time() - start
    s.close()
    return n / elapsed, elapsed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    args = ap.parse_args()

    rps_set, t_set = bench_set(args.n, args.host, args.port)
    rps_get, t_get = bench_get(args.n, args.host, args.port)
    print(f"SET: {args.n} ops in {t_set:.2f}s -> {rps_set:.0f} ops/s")
    print(f"GET: {args.n} ops in {t_get:.2f}s -> {rps_get:.0f} ops/s")
