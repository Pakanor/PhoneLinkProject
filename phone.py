
from zeroconf import Zeroconf, ServiceBrowser
import socket
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
                s.connect((ip,port))
                s.sendall(b"siema dziala")
                data = s.recv(1024)
                print(f"Odpowiedź: {data.decode()}")
                
            

    def update_service(self,zeroconf,type,name):
        pass
        


    def list_devices(self):
        pass
zeroconf = Zeroconf()
browser = ServiceBrowser(zeroconf,"_phonelink._tcp.local.", Phone())
input("Scanning... press Enter to stop\n")
zeroconf.close()

    