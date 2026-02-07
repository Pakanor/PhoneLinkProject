import os
import socket
from Core.DataTransferLayer.handshake import HandshakeManager
import threading
from Core.ConnectionLayer.socket_utils import file_type,user_file_input
from Core.DataTransferLayer.protocol import Message

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
            while True:
                try:
                    print("[Server] Czekam na wiadomość...")
                    received_msg = Message.deserialize(conn, encryption)
                    print(f"[Server] Otrzymano typ: {received_msg.type}, payload: {received_msg.payload}")
                    
                    file_type(received_msg,conn,encryption)
                    
                    #user_file_input(conn,encryption) tu logika wysylania jutro!!!!                 
                except Exception as e:
                    print(f"[Server] Błąd w pętli: {e}")
                    import traceback
                    traceback.print_exc()
                    break
                    
        except Exception as e:
            print(f"[Server] Błąd handlera: {e}")
            import traceback
            traceback.print_exc()