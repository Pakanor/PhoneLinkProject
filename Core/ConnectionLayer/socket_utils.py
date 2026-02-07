import socket
import traceback
import os


class ClientDisconnected(Exception):
    pass

class ClientDisconnected(Exception):
    pass


def recv_all(sock, n):
    data = b""
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))

            if chunk == b"":
                raise ClientDisconnected("zamknieto polaczenie")

            data += chunk

        except ConnectionResetError:
            raise ClientDisconnected("reset polaczenia")

        except socket.timeout:
            raise TimeoutError(f"timeout")

    return data


def user_file_input(s, encryption):
    
    from Core.DataTransferLayer.file_transfer import send_file
    
    while True:
        file_path = input("Ścieżka do pliku (Enter = koniec): ").strip()
        
        if file_path.lower == "exit":
            from Core.DataTransferLayer.protocol import Message
            msg = Message("SHUTDOWN", {"user": "telefon", "action": "disconnect"}, encrypted=True)

            break
        
        if not os.path.exists(file_path):
            print(f"[user_file_input] ⚠️  Plik nie istnieje: {file_path}")
            continue
        
        if not os.path.isfile(file_path):
            print(f"[user_file_input] ⚠️  To nie jest plik: {file_path}")
            continue
        
        try:
            send_file(s, file_path, encryption)
            print(f"[user_file_input] ✓ Plik {file_path} wysłany pomyślnie")
        except Exception as e:
            print(f"[user_file_input] ❌ Błąd: {e}")
            traceback.print_exc()

    return file_path


def file_type(received_msg,conn,encryption):
    from Core.DataTransferLayer.protocol import Message
    from Core.DataTransferLayer.file_transfer import recv_file

    if received_msg.type == "FILE_START":
        filename = received_msg.payload['filename']
        filesize = received_msg.payload['size']
                        
        dest_dir = os.path.join(os.getcwd(), "received_files")
        os.makedirs(dest_dir, exist_ok=True)
                        
        saved = recv_file(conn, dest_dir, filename, filesize, encryption)
        print(f"[Server] Plik zapisany: {saved}")
                        
        response = Message("FILE_ACK", {"status": "OK", "saved_path": saved}, encrypted=True)
        conn.sendall(response.serialize(encryption))
        print("[Server] Wysłano potwierdzenie pliku")
                        
    elif received_msg.type == "GREETING":
        print("[Server] Otrzymano greeting, wysyłam odpowiedź...")
        response = Message("GREETING_ACK", {"status": "OK"}, encrypted=True)
        conn.sendall(response.serialize(encryption))
        print("[Server] Odpowiedź wysłana")
    
                        
    else:
        print(f"[Server] Nieznany typ wiadomości: {received_msg.type}")
        response = Message("ERROR", {"error": "Unknown message type"}, encrypted=True)
        conn.sendall(response.serialize(encryption))

    

