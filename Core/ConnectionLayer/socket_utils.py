import socket
import traceback
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

    return data




def server_handle_message(received_msg,conn,encryption):
    from Core.DataTransferLayer.protocol import Message
    from Core.DataTransferLayer.file_transfer import recv_file
    import os

    if received_msg.type == "GREETING":
        print("[Server] Otrzymano greeting, wysyłam odpowiedź...")
        response = Message("GREETING_ACK", {"status": "OK"}, encrypted=True)
        conn.sendall(response.serialize(encryption))
        print("[Server] GREETING_ACK wysłane")
    
    elif received_msg.type == "FILE_START":
        filename = received_msg.payload['filename']
        filesize = received_msg.payload['size']
        print(f"[Server] Otrzymano FILE_START: {filename} ({filesize} bytes)")
        
        dest_dir = os.path.join(BASE_DIR, "from_clients")
        os.makedirs(dest_dir, exist_ok=True)
        
        saved = recv_file(conn, dest_dir, filename, filesize, encryption)
        print(f"[Server] Plik zapisany: {saved}")
        
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
    from Core.DataTransferLayer.file_transfer import recv_file

    if received_msg.type == "GREETING_ACK":
        print("[Client] Serwer przywitał się OK")

    elif received_msg.type == "FILE_START":
        filename = received_msg.payload['filename']
        filesize = received_msg.payload['size']

        dest_dir = os.path.join(BASE_DIR, "from_server")
        os.makedirs(dest_dir, exist_ok=True)

        saved = recv_file(conn, dest_dir, filename, filesize, encryption)  
        print(f"[Client] Plik zapisany: {saved}")

        response = Message("FILE_ACK", {"status": "OK", "saved_path": saved}, encrypted=True)
        conn.sendall(response.serialize(encryption))


    elif received_msg.type == "FILE_ACK":
        print("[Client] Transfer zakończony")

    elif received_msg.type == "ERROR":
        print("[Client] Błąd:", received_msg.payload)

    else:
        print("[Client] Nieznany typ:", received_msg.type)


