
import argparse
import socket
import threading
from cache import LRUCache
from protocol import ProtocolHandler


def handle_client(cache: LRUCache, conn: socket.socket, addr):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    def send(data: bytes):
        try:
            conn.sendall(data)
        except Exception:
            pass
    handler = ProtocolHandler(cache, send)
    try:
        with conn:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                handler.on_data(data)
    except Exception:
        # Let the connection drop silently; server keeps running
        pass


def serve(host: str, port: int, capacity_mb: int):
    cache = LRUCache(capacity_bytes=capacity_mb * 1024 * 1024)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(512)
        print(f"Cache server listening on {host}:{port} (capacity={capacity_mb} MB)")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(cache, conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--capacity-mb", type=int, default=64)
    args = ap.parse_args()
    serve(args.host, args.port, args.capacity_mb)
