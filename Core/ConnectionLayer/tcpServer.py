import socket


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
                    with conn:
                        print(f"Połączono z {addr}")
                        self.handle_client(conn)
                except Exception as e:
                    print(f"Błąd: {e}")
                
    def stop(self):
        self.running = False
    
    def handle_client(self, conn):
        try:
            data = conn.recv(1024)
            if data:
                print(f"Otrzymano: {data.decode()}")
                conn.sendall(b"OK")
        except Exception as e:
            print(f"Błąd handlera: {e}")