import socket
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.handshake import HandshakeManager


class tcpServer:
    def __init__(self,host,port):
        self.host = host
        self.port = port
        self.running = False
        
    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.bind((self.host,self.port))
            s.listen()
            print(f"Serwer słucha na {self.host}:{self.port}")
            while self.running:
                try:
                    conn, addr = s.accept()
                    conn.settimeout(30)
                    with conn:
                        print(f"Połączono z {addr}")
                        self.handle_client(conn)
                except Exception as e:
                    print(f"Błąd: {e}")
                
    def stop(self):
        self.running = False
    
    def handle_client(self, conn):
        try:
            encryption = HandshakeManager.server_handshake(conn)
            print("[Server] Klucz szyfrowania ustalony")
            
            print("[Server] Czekam na wiadomość...")
            received_msg = Message.deserialize(conn, encryption)
            print(f"[Server] Otrzymano typ: {received_msg.type}, payload: {received_msg.payload}")
            
            print("[Server] Wysyłam odpowiedź...")
            response = Message("RESPONSE", {"status": "OK", "message": "Wiadomość odebrana"}, encrypted=True)
            conn.sendall(response.serialize(encryption))
            print("[Server] Odpowiedź wysłana")
        except Exception as e:
            print(f"[Server] Błąd handlera: {e}")
            import traceback
            traceback.print_exc()