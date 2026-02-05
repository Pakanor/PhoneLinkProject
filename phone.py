
from zeroconf import Zeroconf, ServiceBrowser
import socket
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.handshake import HandshakeManager

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
                s.settimeout(30)
                s.connect((ip,port))
                
                encryption = HandshakeManager.client_handshake(s)
                print("[Klient] Klucz szyfrowania ustalony")
                
                print("[Klient] Wysyłam wiadomość...")
                msg = Message("GREETING", {"user": "telefon", "action": "connect"}, encrypted=True)
                s.sendall(msg.serialize(encryption))
                print("[Klient] Wiadomość wysłana, czekam na odpowiedź...")
                
                response = Message.deserialize(s, encryption)
                print(f"[Klient] Odpowiedź typ: {response.type}, payload: {response.payload}")
                
            

    def update_service(self,zeroconf,type,name):
        pass
        


    def list_devices(self):
        pass

zeroconf = Zeroconf()
browser = ServiceBrowser(zeroconf,"_phonelink._tcp.local.", Phone())
input("Scanning... press Enter to stop\n")
zeroconf.close()