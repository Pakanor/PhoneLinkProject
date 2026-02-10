import os
import socket
from Core.DataTransferLayer.handshake import HandshakeManager
import threading
from Core.ConnectionLayer.socket_utils import server_handle_message,user_file_input
from Core.DataTransferLayer.protocol import Message



class tcpServer:
    def __init__(self,host,port):
        self.host = host
        self.port = port
        self.running = False
        self.client = None
   
    
    
    def send_file_to_client(self, filename):
        import os
        from Core.DataTransferLayer.protocol import Message
        from Core.DataTransferLayer.file_transfer import send_file
        
        file_path = os.path.join(os.getcwd(), filename)
        
        if not os.path.exists(file_path):
            print(f"[Server]  Plik nie istnieje: {file_path}")
            return
        
        
        if not self.client:
            print("[Server]  Brak podłączonych klientów")
            return
        conn, encryption = self.client  
        
        try:
            file_size = os.path.getsize(file_path)
            file_start_msg = Message("FILE_START", {"filename": filename, "size": file_size}, encrypted=True)
            conn.sendall(file_start_msg.serialize(encryption))
            print(f"[Server]  FILE_START wysłane: {filename} ({file_size} bytes)")
            
            send_file(conn, file_path, encryption)
            print(f"[Server] Plik {filename} wysłany pomyślnie")
        except Exception as e:
            print(f"[Server] Błąd wysyłania: {e}")
            import traceback
            traceback.print_exc()
        
        
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
            self.client = (conn, encryption)
            while True:
                try:
                    print("[Server] Czekam na wiadomość...")
                    received_msg = Message.deserialize(conn, encryption)
                    print(f"[Server] Otrzymano typ: {received_msg.type}, payload: {received_msg.payload}")
                    
                    server_handle_message(received_msg, conn, encryption)
             
                except Exception as e:
                    print(f"[Server] Błąd w pętli: {e}")
                    import traceback
                    traceback.print_exc()
                    break
                    
        except Exception as e:
            print(f"[Server] Błąd handlera: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.remove_client()

    def remove_client(self):
        if self.client:
            try:
                self.client[0].close()
            except:
                pass
            self.client = None