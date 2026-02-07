from zeroconf import Zeroconf, ServiceBrowser
import socket
import time
import threading

from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.handshake import HandshakeManager
from Core.ConnectionLayer.socket_utils import user_file_input


class Phone:
    def __init__(self):
        self.ip = None
        self.port = None
        self.found_event = threading.Event()

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            self.ip = socket.inet_ntoa(info.addresses[0])
            self.port = info.port
            print(f"[Zeroconf] Found service {name} at {self.ip}:{self.port}")
            self.found_event.set()


phone = Phone()
zeroconf = Zeroconf()
browser = ServiceBrowser(zeroconf, "_phonelink._tcp.local.", phone)

print("Scanning...")

phone.found_event.wait()  
zeroconf.close()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(300)
    s.connect((phone.ip, phone.port))

    encryption = HandshakeManager.client_handshake(s)
    print("[Klient] Klucz szyfrowania ustalony")

    msg = Message("GREETING", {"user": "telefon", "action": "connect"}, encrypted=True)
    s.sendall(msg.serialize(encryption))

    response = Message.deserialize(s, encryption)
    print(f"[Klient] Odpowiedź typ: {response.type}, payload: {response.payload}")

    user_file_input(s, encryption)

