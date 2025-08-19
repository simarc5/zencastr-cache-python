
import socket


def send_cmd(cmd: str, payload: bytes = b""):
    with socket.create_connection(("127.0.0.1", 9000)) as s:
        s.sendall(cmd.encode() + b"\n" + payload)
        out = s.recv(1 << 16)
        print(out.decode(errors="ignore"), end="")


if __name__ == "__main__":
    # demo
    send_cmd("SET greeting 3000 5", b"hello\n")
    send_cmd("GET greeting")
    send_cmd("DEL greeting")
    send_cmd("GET greeting")
    send_cmd("STATS")
