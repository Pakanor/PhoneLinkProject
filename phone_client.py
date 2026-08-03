import argparse
import hashlib
import os
import signal
import socket
import sys
import threading

from Core.DataTransferLayer.handshake import HandshakeManager
from Core.DataTransferLayer.protocol import Message
from Core.ConnectionLayer.socket_utils import client_handle_message, ClientDisconnected
from Core.ConnectionLayer.client_discovery import ServerDiscovery


class PhoneClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.encryption = None
        self.running = False
        self._listener_thread = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        self.sock.connect((self.host, self.port))
        self.encryption = HandshakeManager.client_handshake(self.sock)
        print("[Klient] Handshake ECDH zakończony, klucz AES-256-GCM ustalony")

        greeting = Message("GREETING", {"user": "cli", "action": "connect"}, encrypted=True)
        self.sock.sendall(greeting.serialize(self.encryption))
        response = Message.deserialize(self.sock, self.encryption)
        if response.type != "GREETING_ACK":
            raise Exception(f"Oczekiwano GREETING_ACK, otrzymano {response.type}")
        print(f"[Klient] Połączono z {self.host}:{self.port}")

    def start_listener(self):
        self.running = True
        self._listener_thread = threading.Thread(target=self._listen, daemon=True)
        self._listener_thread.start()

    def _listen(self):
        while self.running:
            try:
                msg = Message.deserialize(self.sock, self.encryption)
                client_handle_message(msg, self.sock, self.encryption)
            except ClientDisconnected as e:
                print(f"[Klient] Serwer rozłączył się: {e}")
                break
            except Exception as e:
                print(f"[Klient] Błąd w wątku odbierającym: {e}")
                break
        self.running = False

    def send_file(self, filepath):
        from Core.DataTransferLayer.file_transfer import send_file

        if not os.path.exists(filepath):
            print(f"[Klient] Plik nie istnieje: {filepath}")
            return False

        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)

        meta = Message(
            "FILE_START",
            {"filename": filename, "size": file_size, "sha256": hasher.hexdigest()},
            encrypted=True
        )
        self.sock.sendall(meta.serialize(self.encryption))
        send_file(self.sock, filepath, self.encryption, send_metadata=False)
        print(f"[Klient] Plik {filename} wysłany")
        return True

    def close(self):
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2)


def _run_repl(client):
    print("Dostępne komendy: send <ścieżka_do_pliku> | status | exit")
    try:
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            if cmd == "exit":
                break
            elif cmd == "status":
                state = "aktywny" if client.running else "zakończony"
                print(f"[Klient] Połączono z {client.host}:{client.port}, nasłuch: {state}")
            elif cmd == "send":
                if len(parts) < 2:
                    print("Użycie: send <ścieżka_do_pliku>")
                    continue
                client.send_file(parts[1])
            else:
                print("Nieznana komenda. Dostępne: send <ścieżka> | status | exit")
    finally:
        client.close()
        print("[Klient] Zakończono")


def main():
    parser = argparse.ArgumentParser(description="PhoneLink – klient CLI (P2P transfer plików)")
    parser.add_argument("--host", help="Adres IP serwera (domyślnie wykrywany przez mDNS)")
    parser.add_argument("--port", type=int, default=5000, help="Port serwera (domyślnie 5000)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Timeout odkrywania mDNS (s)")
    args = parser.parse_args()

    if args.host:
        host, port = args.host, args.port
    else:
        try:
            host, port = ServerDiscovery(timeout=args.timeout).find_server()
            print(f"[Klient] Znaleziono serwer: {host}:{port}")
        except TimeoutError as e:
            print(f"[Klient] {e}")
            return 1

    client = PhoneClient(host, port)
    signal.signal(signal.SIGINT, lambda *a: client.close())

    try:
        client.connect()
    except Exception as e:
        print(f"[Klient] Nie udało się połączyć: {e}")
        return 1

    client.start_listener()
    _run_repl(client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
