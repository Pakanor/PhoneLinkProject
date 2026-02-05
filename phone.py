
from zeroconf import Zeroconf, ServiceBrowser
import socket
import time
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.handshake import HandshakeManager
from Core.DataTransferLayer.file_transfer import send_file

class Phone:
    def add_service(self,zeroconf,type,name):

        print(f'{name}')
        info = zeroconf.get_service_info(type,name)
        if info:
            print("IP:", ".".join(map(str, info.addresses[0])))
            print("Port:", info.port)
            print("Properties:", {k.decode(): v.decode() for k, v in info.properties.items()})
            ip = socket.inet_ntoa(info.addresses[0])
            port = info.port
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.settimeout(300)  
                s.connect((ip,port))
                
                encryption = HandshakeManager.client_handshake(s)
                print("[Klient] Klucz szyfrowania ustalony")
                
                print("[Klient] Wysyłam greeting...")
                msg = Message("GREETING", {"user": "telefon", "action": "connect"}, encrypted=True)
                s.sendall(msg.serialize(encryption))
                print("[Klient] Wiadomość wysłana, czekam na odpowiedź...")
                
                response = Message.deserialize(s, encryption)
                print(f"[Klient] Odpowiedź typ: {response.type}, payload: {response.payload}")
                import os
                
                while True:
                    file_path = input("Ścieżka do pliku (Enter = koniec): ").strip()
                    
                    if not file_path:
                        print("[Klient] Koniec wysyłania plików")
                        break
                    
                    if not os.path.exists(file_path):
                        print(f"[Klient] ⚠️  Plik nie istnieje: {file_path}")
                        continue
                    
                    if not os.path.isfile(file_path):
                        print(f"[Klient] ⚠️  To nie jest plik: {file_path}")
                        continue
                    
                    try:
                        send_file(s, file_path, encryption)
                        print(f"[Klient] ✓ Plik {file_path} wysłany pomyślnie")
                    except Exception as e:
                        print(f"[Klient] ❌ Błąd: {e}")
                        import traceback
                        traceback.print_exc()
                    
                

    def update_service(self,zeroconf,type,name):
        pass
        


    def list_devices(self):
        pass

zeroconf = Zeroconf()
browser = ServiceBrowser(zeroconf, "_phonelink._tcp.local.", Phone())
print("Scanning... press Ctrl+C to stop")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    zeroconf.close()