from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.encryption import Encryption


class HandshakeManager:

    PROTOCOL_VERSION = "1.0"
    SUPPORTED_CIPHERS = ["AES-256-GCM"]

    @staticmethod
    def client_handshake(sock) -> Encryption:
        client_priv = Encryption.generate_key_pair()

        handshake_msg = Message(
            "HANDSHAKE",
            {
                "version": HandshakeManager.PROTOCOL_VERSION,
                "supported_ciphers": HandshakeManager.SUPPORTED_CIPHERS,
                "client_pub_key": Encryption.public_key_b64(client_priv),
            }
        )
        sock.sendall(handshake_msg.serialize())

        ack_msg = Message.deserialize(sock)
        if ack_msg.type != "HANDSHAKE_ACK":
            raise Exception(f"Oczekiwano HANDSHAKE_ACK, otrzymano {ack_msg.type}")

        server_pub_key = ack_msg.payload.get("server_pub_key")
        if not server_pub_key:
            raise Exception("Brak klucza publicznego serwera w HANDSHAKE_ACK")

        shared_key = Encryption.derive_shared_key(client_priv, server_pub_key)
        encryption = Encryption(shared_key)

        ack_confirmation = Message("HANDSHAKE_DONE", {"status": "OK"}, encrypted=True)
        sock.sendall(ack_confirmation.serialize(encryption))

        return encryption

    @staticmethod
    def server_handshake(sock) -> Encryption:
        handshake_msg = Message.deserialize(sock)
        if handshake_msg.type != "HANDSHAKE":
            raise Exception(f"Oczekiwano HANDSHAKE, otrzymano {handshake_msg.type}")

        client_pub_key = handshake_msg.payload.get("client_pub_key")
        if not client_pub_key:
            raise Exception("Brak klucza publicznego klienta w HANDSHAKE")

        server_priv = Encryption.generate_key_pair()

        shared_key = Encryption.derive_shared_key(server_priv, client_pub_key)
        encryption = Encryption(shared_key)

        ack_msg = Message(
            "HANDSHAKE_ACK",
            {
                "cipher_selected": "AES-256-GCM",
                "server_pub_key": Encryption.public_key_b64(server_priv),
            }
        )
        sock.sendall(ack_msg.serialize())

        confirmation = Message.deserialize(sock, encryption)
        if confirmation.type != "HANDSHAKE_DONE":
            raise Exception(f"Oczekiwano HANDSHAKE_DONE, otrzymano {confirmation.type}")

        return encryption
