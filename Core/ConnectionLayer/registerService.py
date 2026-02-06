
from zeroconf import Zeroconf, ServiceInfo
import socket
import time
class RegisterService:
    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8",80))
            ip = s.getsockname()[0]
        except:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip



    def connect(self):
        service_type = "_phonelink._tcp.local."
        service_name = "PhoneLink-Robert._phonelink._tcp.local."
        port = 5000
        ip = socket.inet_aton(self.get_local_ip())

        properties = {
            b"id": b"123456",
            b"version": b"1",
            b"cap": b"file,clipboard"
        }


        info = ServiceInfo(
            service_type,
            service_name,
            addresses=[ip],
            port=port,
            properties=properties
        )

        zeroconf = Zeroconf()
        zeroconf.register_service(info)
        time.sleep(5)
if __name__ == "__main__":
    service = RegisterService()
    service.connect()    