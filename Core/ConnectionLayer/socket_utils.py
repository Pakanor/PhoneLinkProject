import socket
import os

BASE_DIR = os.path.expanduser("~/PhoneLink_received")
class ClientDisconnected(Exception):
    pass



def recv_all(sock, n):
    data = b""
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))

            if chunk == b"":
                raise ClientDisconnected(f"zamknieto polaczenie (received {len(data)}/{n} bytes)")

            data += chunk

        except ConnectionResetError:
            raise ClientDisconnected("reset polaczenia")

        except socket.timeout:
            raise TimeoutError(f"timeout (received {len(data)}/{n} bytes)")

        except OSError:
            raise ClientDisconnected("socket zamkniety przez serwer")

    return data




def server_handle_message(received_msg, conn, encryption, event_queue=None, client_id=None):
    from Core.DataTransferLayer.protocol import Message
    from Core.DataTransferLayer.file_transfer import recv_file, SHA256Mismatch, sanitize_filename
    import os

    def _emit(event_type, data=None):
        if event_queue is not None:
            try:
                event_queue.put((event_type, data or {}))
            except Exception:
                pass

    if received_msg.type == "GREETING":
        print("[Server] Otrzymano greeting, wysyłam odpowiedź...")
        _emit("log", {"message": f"Klient {client_id} wysłał GREETING"})
        response = Message("GREETING_ACK", {"status": "OK"}, encrypted=True)
        conn.sendall(response.serialize(encryption))
        print("[Server] GREETING_ACK wysłane")

    elif received_msg.type == "FILE_START":
        filename = received_msg.payload['filename']
        filesize = received_msg.payload['size']
        expected_sha256 = received_msg.payload.get('sha256')
        try:
            filename = sanitize_filename(filename)
        except ValueError:
            print("[Server] Odrzucono FILE_START z nieprawidłową nazwą pliku")
            response = Message("ERROR", {"error": "Invalid filename"}, encrypted=True)
            conn.sendall(response.serialize(encryption))
            _emit("transfer_complete", {
                "client_id": client_id,
                "filename": filename,
                "direction": "recv",
                "ok": False,
                "error": "Invalid filename",
            })
            raise
        print(f"[Server] Otrzymano FILE_START: {filename} ({filesize} bytes)")
        _emit("log", {"message": f"Odbieram {filename} ({filesize} B) od {client_id}"})

        dest_dir = os.path.join(BASE_DIR, "from_clients")
        os.makedirs(dest_dir, exist_ok=True)

        def _progress(sent, total, speed_mbps):
            _emit("transfer_progress", {
                "client_id": client_id,
                "filename": filename,
                "direction": "recv",
                "sent": sent,
                "total": total,
                "speed_mbps": speed_mbps,
            })

        try:
            saved = recv_file(conn, dest_dir, filename, filesize, encryption,
                              expected_sha256=expected_sha256, progress_callback=_progress)
        except SHA256Mismatch as e:
            print(f"[Server] {e}, wysyłam ERROR do nadawcy")
            response = Message("ERROR", {"error": str(e)}, encrypted=True)
            conn.sendall(response.serialize(encryption))
            _emit("log", {"message": f"Błąd SHA-256 pliku {filename} od {client_id}"})
            _emit("transfer_complete", {
                "client_id": client_id,
                "filename": filename,
                "direction": "recv",
                "ok": False,
                "error": str(e),
            })
            raise

        print(f"[Server] Plik zapisany: {saved}")
        _emit("log", {"message": f"Odebrano plik {filename} - SHA-256 OK"})
        _emit("transfer_complete", {
            "client_id": client_id,
            "filename": filename,
            "direction": "recv",
            "ok": True,
            "saved_path": saved,
        })

        response = Message("FILE_ACK", {"status": "OK", "saved_path": saved}, encrypted=True)
        conn.sendall(response.serialize(encryption))
        print("[Server] Wysłano potwierdzenie pliku")
    
    elif received_msg.type == "FILE_ACK":
        print("[Server] Klient potwierdził otrzymanie pliku")
        print(f"[Server] Zapisany pod: {received_msg.payload.get('saved_path')}")
                        
    else:
        print(f"[Server] Nieznany typ wiadomości: {received_msg.type}")
        response = Message("ERROR", {"error": "Unknown message type"}, encrypted=True)
        conn.sendall(response.serialize(encryption))

    
def client_handle_message(received_msg, conn, encryption):
    from Core.DataTransferLayer.protocol import Message
    from Core.DataTransferLayer.file_transfer import recv_file, SHA256Mismatch, sanitize_filename

    if received_msg.type == "GREETING_ACK":
        print("[Client] Serwer przywitał się OK")

    elif received_msg.type == "FILE_START":
        filename = received_msg.payload['filename']
        filesize = received_msg.payload['size']
        expected_sha256 = received_msg.payload.get('sha256')
        try:
            filename = sanitize_filename(filename)
        except ValueError:
            print("[Client] Odrzucono FILE_START z nieprawidłową nazwą pliku")
            response = Message("ERROR", {"error": "Invalid filename"}, encrypted=True)
            conn.sendall(response.serialize(encryption))
            raise

        dest_dir = os.path.join(BASE_DIR, "from_server")
        os.makedirs(dest_dir, exist_ok=True)

        try:
            saved = recv_file(conn, dest_dir, filename, filesize, encryption,
                              expected_sha256=expected_sha256)
        except SHA256Mismatch as e:
            print(f"[Client] {e}, wysyłam ERROR do nadawcy")
            response = Message("ERROR", {"error": str(e)}, encrypted=True)
            conn.sendall(response.serialize(encryption))
            raise

        print(f"[Client] Plik zapisany: {saved}")

        response = Message("FILE_ACK", {"status": "OK", "saved_path": saved}, encrypted=True)
        conn.sendall(response.serialize(encryption))


    elif received_msg.type == "FILE_ACK":
        print("[Client] Transfer zakończony")

    elif received_msg.type == "ERROR":
        print("[Client] Błąd:", received_msg.payload)

    else:
        print("[Client] Nieznany typ:", received_msg.type)


