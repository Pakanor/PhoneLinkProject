import os
import socket
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.handshake import HandshakeManager
from Core.DataTransferLayer.file_transfer import recv_file
import threading
from Core.ConnectionLayer.socket_utils import user_file_input

class tcpServer:
    def __init__(self,host,port):
        self.host = host
        self.port = port
        self.running = False
        
    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"Serwer słucha na {self.host}:{self.port}")
            while self.running:
                try:
                    conn, addr = s.accept()
                    print(f"Połączono z {addr}")
                    conn.settimeout(300)
                    
                    t = threading.Thread(target=self.handle_client, args=(conn,))
                    t.start()
                    
                except Exception as e:
                    print(f"Błąd: {e}")
                
    def stop(self):
        self.running = False
    
    def handle_client(self, conn):
        try:
            encryption = HandshakeManager.server_handshake(conn)
            print("[Server] Klucz szyfrowania ustalony")
            sender_thread = threading.Thread(target=user_file_input, args=(conn, encryption), daemon=True)
            sender_thread.start()
            
            while True:
                try:
                    print("[Server] Czekam na wiadomość...")
                    received_msg = Message.deserialize(conn, encryption)
                    print(f"[Server] Otrzymano typ: {received_msg.type}, payload: {received_msg.payload}")
                    
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
                        
                except Exception as e:
                    print(f"[Server] Błąd w pętli: {e}")
                    import traceback
                    traceback.print_exc()
                    break
                    
        except Exception as e:
            print(f"[Server] Błąd handlera: {e}")
            import traceback
            traceback.print_exc()