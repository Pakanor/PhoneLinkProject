import socket
import threading
import time
import uuid
from Core.DataTransferLayer.handshake import HandshakeManager
from Core.ConnectionLayer.socket_utils import server_handle_message, ClientDisconnected
from Core.DataTransferLayer.protocol import Message


class ClientSession:
    def __init__(self, client_id, conn, addr, encryption):
        self.client_id = client_id
        self.conn = conn
        self.addr = addr
        self.encryption = encryption
        self.connected_at = time.time()


class tcpServer:
    def __init__(self, host, port, event_queue=None):
        self.host = host
        self.port = port
        self.running = False
        self.clients = {}
        self._lock = threading.Lock()
        self._listen_socket = None
        self.event_queue = event_queue

    def _emit(self, event_type, data=None):
        if self.event_queue is not None:
            try:
                self.event_queue.put((event_type, data or {}))
            except Exception:
                pass

    @staticmethod
    def _close_connection(conn):
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass

    def add_client(self, session):
        with self._lock:
            self.clients[session.client_id] = session
        return session.client_id

    def remove_client(self, client_id):
        with self._lock:
            session = self.clients.pop(client_id, None)
        if session:
            self._close_connection(session.conn)
        return session

    def get_client(self, client_id):
        with self._lock:
            return self.clients.get(client_id)

    def get_client_ids(self):
        with self._lock:
            return list(self.clients.keys())

    def get_clients_snapshot(self):
        with self._lock:
            return [
                {"client_id": s.client_id, "addr": s.addr, "connected_at": s.connected_at}
                for s in self.clients.values()
            ]

    def disconnect_all_clients(self):
        with self._lock:
            sessions = list(self.clients.values())
            self.clients.clear()
        for session in sessions:
            self._close_connection(session.conn)

    @staticmethod
    def _generate_client_id(addr):
        return f"{addr[0]}-{addr[1]}-{uuid.uuid4().hex[:8]}"

    def send_file_to_client(self, file_path, client_id=None, mode="server"):
        import os
        import hashlib
        from Core.DataTransferLayer.protocol import Message
        from Core.DataTransferLayer.file_transfer import send_file

        if client_id is None:
            ids = self.get_client_ids()
            if not ids:
                print("[Server]  Brak podłączonych klientów")
                return
            if len(ids) > 1:
                print("[Server]  Podłączonych jest więcej niż jeden klient – podaj client_id")
                return
            client_id = ids[0]

        session = self.get_client(client_id)
        if session is None:
            print(f"[Server]  Nie znaleziono klienta: {client_id}")
            return

        if not os.path.exists(file_path):
            print(f"[Server]  Plik nie istnieje: {file_path}")
            self._emit("log", {"message": f"Plik nie istnieje: {file_path}"})
            return

        conn = session.conn
        encryption = session.encryption

        try:
            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            file_sha256 = hasher.hexdigest()
            file_start_msg = Message(
                "FILE_START",
                {"filename": filename, "size": file_size, "sha256": file_sha256},
                encrypted=True
            )
            conn.sendall(file_start_msg.serialize(encryption))
            print(f"[Server]  FILE_START wysłane: {filename} ({file_size} bytes) do {client_id}")
            self._emit("log", {"message": f"Wysyłam {filename} ({file_size} B) do {client_id}"})

            def _progress(sent, total, speed_mbps):
                self._emit("transfer_progress", {
                    "client_id": client_id,
                    "filename": filename,
                    "direction": "send",
                    "sent": sent,
                    "total": total,
                    "speed_mbps": speed_mbps,
                })

            send_file(conn, file_path, encryption, send_metadata=False,
                      progress_callback=_progress)
            print(f"[Server] Plik {filename} wysłany pomyślnie do {client_id}")
            self._emit("log", {"message": f"Plik {filename} wysłany do {client_id}"})
            self._emit("transfer_complete", {
                "client_id": client_id,
                "filename": filename,
                "direction": "send",
                "ok": True,
            })
        except Exception as e:
            print(f"[Server] Błąd wysyłania: {e}")
            import traceback
            traceback.print_exc()
            self._emit("log", {"message": f"Błąd wysyłania {filename}: {e}"})
            self._emit("transfer_complete", {
                "client_id": client_id,
                "filename": filename,
                "direction": "send",
                "ok": False,
                "error": str(e),
            })

    def start(self):
        self.running = True
        self._listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listen_socket.bind((self.host, self.port))
        self.port = self._listen_socket.getsockname()[1]
        self._listen_socket.listen()
        self._listen_socket.settimeout(1.0)
        print(f"Serwer słucha na {self.host}:{self.port}")
        while self.running:
            try:
                conn, addr = self._listen_socket.accept()
                print(f"Połączono z {addr}")
                conn.settimeout(3600)
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def stop(self):
        self.running = False
        if self._listen_socket:
            try:
                self._listen_socket.close()
            except OSError:
                pass
            self._listen_socket = None
        self.disconnect_all_clients()

    def handle_client(self, conn, addr):
        client_id = self._generate_client_id(addr)
        try:
            encryption = HandshakeManager.server_handshake(conn)
            print("[Server] Klucz szyfrowania ustalony")
            self.add_client(ClientSession(client_id, conn, addr, encryption))
            print(f"[Server] Klient {client_id} zarejestrowany")
            self._emit("log", {"message": f"Nawiązano połączenie ECDH z {addr[0]}:{addr[1]}"})
            self._emit("client_connected", {"client_id": client_id, "addr": addr})
            while True:
                print("[Server] Czekam na wiadomość...")
                received_msg = Message.deserialize(conn, encryption)
                print(f"[Server] Otrzymano typ: {received_msg.type}, payload: {received_msg.payload}")
                server_handle_message(received_msg, conn, encryption,
                                      event_queue=self.event_queue, client_id=client_id)
        except ClientDisconnected as e:
            print(f"[Server] Klient {client_id} rozłączył się: {e}")
        except Exception as e:
            print(f"[Server] Błąd handlera: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session = self.remove_client(client_id)
            if session is None:
                self._close_connection(conn)
            print(f"[Server] Klient {client_id} odłączony")
            self._emit("client_disconnected", {"client_id": client_id})
