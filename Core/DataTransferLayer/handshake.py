import json
import base64
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.encryption import Encryption

class HandshakeManager:
    
    PROTOCOL_VERSION = "1.0"
    SUPPORTED_CIPHERS = ["AES-256-GCM"]
    
    @staticmethod
    def client_handshake(sock) -> Encryption:
        
        
        handshake_msg = Message(
            "HANDSHAKE",
            {
                "version": HandshakeManager.PROTOCOL_VERSION,
                "supported_ciphers": HandshakeManager.SUPPORTED_CIPHERS
            }
        )
        sock.sendall(handshake_msg.serialize())
        
        ack_msg = Message.deserialize(sock)
        if ack_msg.type != "HANDSHAKE_ACK":
            raise Exception(f"Oczekiwano HANDSHAKE_ACK, otrzymano {ack_msg.type}")
        
        cipher = ack_msg.payload.get("cipher_selected")
        server_key_b64 = ack_msg.payload.get("server_key")
        
        
        encryption = Encryption.from_b64(server_key_b64)
        
        ack_confirmation = Message("HANDSHAKE_DONE", {"status": "OK"}, encrypted=True)
        sock.sendall(ack_confirmation.serialize(encryption))
        
        return encryption
    
    @staticmethod
    def server_handshake(sock) -> Encryption:
        
        
        handshake_msg = Message.deserialize(sock)
        if handshake_msg.type != "HANDSHAKE":
            raise Exception(f"Oczekiwano HANDSHAKE, otrzymano {handshake_msg.type}")
        
        
        encryption = Encryption()  
        key_b64 = encryption.get_key_b64()
        
        ack_msg = Message(
            "HANDSHAKE_ACK",
            {
                "cipher_selected": "AES-256-GCM",
                "server_key": key_b64
            }
        )
        sock.sendall(ack_msg.serialize())
        
        try:
            confirmation = Message.deserialize(sock, encryption)
            if confirmation.type != "HANDSHAKE_DONE":
                print(f"[Handshake] Server: Uwaga - oczekiwano HANDSHAKE_DONE, otrzymano {confirmation.type}")
        except Exception as e:
            print(f"[Handshake] Server: Błąd przy odbieraniu confirmation: {e}")
        
        return encryption
