import pytest
import socket
import threading
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.DataTransferLayer.handshake import HandshakeManager
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.encryption import Encryption, DecryptionError


def test_handshake_flow():
    server_encryption = None
    client_encryption = None
    error = None

    def run_server(server_socket):
        nonlocal server_encryption, error
        try:
            conn, _ = server_socket.accept()
            conn.settimeout(5)
            server_encryption = HandshakeManager.server_handshake(conn)
            conn.close()
        except Exception as e:
            error = f"Server error: {e}"

    def run_client(host, port):
        nonlocal client_encryption, error
        try:
            time.sleep(0.1)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((host, port))
            client_encryption = HandshakeManager.client_handshake(s)
            s.close()
        except Exception as e:
            error = f"Client error: {e}"

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]

    server_thread = threading.Thread(target=run_server, args=(server_socket,))
    client_thread = threading.Thread(target=run_client, args=("127.0.0.1", port))

    server_thread.start()
    client_thread.start()

    server_thread.join(timeout=10)
    client_thread.join(timeout=10)
    server_socket.close()

    assert error is None, f"Error occurred: {error}"
    assert server_encryption is not None, "Server encryption nie została ustawiona"
    assert client_encryption is not None, "Client encryption nie została ustawiona"
    assert server_encryption.shared_key == client_encryption.shared_key, \
        "Klucze klienta i serwera powinny być identyczne"
    assert len(server_encryption.shared_key) == Encryption.KEY_SIZE


def test_message_encrypted_transmission():
    enc = Encryption()

    msg = Message("TEST", {"data": "secret"}, encrypted=True)
    serialized = msg.serialize(enc)

    data = serialized

    import struct
    length = struct.unpack("!I", data[:4])[0]
    encrypted_data = data[4:]

    decrypted = enc.decrypt(encrypted_data)
    message_dict = __import__('json').loads(decrypted.decode('utf-8'))

    assert message_dict["type"] == "TEST"
    assert message_dict["payload"]["data"] == "secret"


def test_deserialize_tampered_ciphertext_raises():
    left, right = socket.socketpair()

    enc = Encryption()
    msg = Message("FILE_START", {"filename": "x", "size": 1, "sha256": "a"}, encrypted=True)
    serialized = bytearray(msg.serialize(enc))
    serialized[-1] ^= 0x01

    left.sendall(bytes(serialized))

    with pytest.raises(DecryptionError):
        Message.deserialize(right, encryption=enc)

    left.close()
    right.close()


def test_plaintext_injection_after_handshake_raises():
    left, right = socket.socketpair()
    result = {}

    def server_task():
        try:
            HandshakeManager.server_handshake(right)
            result["ok"] = True
        except Exception as e:
            result["err"] = e

    t = threading.Thread(target=server_task, daemon=True)
    t.start()

    client_priv = Encryption.generate_key_pair()
    hs = Message(
        "HANDSHAKE",
        {
            "version": "1.0",
            "supported_ciphers": ["AES-256-GCM"],
            "client_pub_key": Encryption.public_key_b64(client_priv),
        }
    )
    left.sendall(hs.serialize())

    ack = Message.deserialize(left)
    assert ack.type == "HANDSHAKE_ACK"
    assert "server_pub_key" in ack.payload, "HANDSHAKE_ACK musi zawierać klucz publiczny"
    assert "server_key" not in ack.payload, "Żaden symetryczny klucz nie może być przesyłany jawnie"

    plain = Message("HANDSHAKE_DONE", {"status": "OK"}, encrypted=False).serialize()
    left.sendall(plain)

    t.join(timeout=5)
    left.close()
    right.close()

    assert not result.get("ok"), "Serwer nie powinien zaakceptować jawnej ramki po handshake"
    assert "err" in result, "Serwer musi przerwać połączenie przy wstrzyknięciu jawnej ramki"


def test_no_raw_key_in_handshake_payloads():
    client_priv = Encryption.generate_key_pair()
    server_priv = Encryption.generate_key_pair()

    handshake = Message(
        "HANDSHAKE",
        {
            "version": "1.0",
            "supported_ciphers": ["AES-256-GCM"],
            "client_pub_key": Encryption.public_key_b64(client_priv),
        }
    )
    ack = Message(
        "HANDSHAKE_ACK",
        {
            "cipher_selected": "AES-256-GCM",
            "server_pub_key": Encryption.public_key_b64(server_priv),
        }
    )

    serialized_wire = handshake.serialize() + ack.serialize()
    assert b"shared_key" not in serialized_wire
    assert b"server_key" not in serialized_wire
    assert handshake.payload.get("client_pub_key") is not None
    assert ack.payload.get("server_pub_key") is not None
