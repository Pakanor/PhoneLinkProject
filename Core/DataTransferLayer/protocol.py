import json
import struct
import base64
from Core.ConnectionLayer.socket_utils import recv_all
from Core.DataTransferLayer.encryption import Encryption

class Message:

    def __init__(self, msg_type: str, payload: dict, encrypted: bool = False):
        self.type = msg_type
        self.payload = payload
        self.encrypted = encrypted

    def serialize(self, encryption: Encryption = None) -> bytes:
        message_dict = {
            "type": self.type,
            "payload": self.payload
        }
        json_data = json.dumps(message_dict).encode('utf-8')
        
        if encryption and self.encrypted:
            json_data = encryption.encrypt(json_data)
        
        length_prefix = struct.pack("!I", len(json_data))
        return length_prefix + json_data

    @staticmethod
    def deserialize(sock, encryption: Encryption = None) -> "Message":
        length_bytes = recv_all(sock, 4)
        message_length = struct.unpack("!I", length_bytes)[0]
        
        data = recv_all(sock, message_length)
        
        if encryption:
            try:
                data = encryption.decrypt(data)
            except Exception as e:
                print(f"[Deszyfrowanie] Błąd: {e}, wiadomość może być niezaszyfrowana")
        
        message_dict = json.loads(data.decode('utf-8'))
        
        return Message(message_dict["type"], message_dict["payload"], encrypted=encryption is not None)
