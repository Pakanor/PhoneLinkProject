import pytest
import socket
import threading
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.DataTransferLayer.handshake import HandshakeManager
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.encryption import Encryption


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


def test_message_encrypted_transmission():
    enc = Encryption()
    
    msg = Message("TEST", {"data": "secret"}, encrypted=True)
    serialized = msg.serialize(enc)
    
    from io import BytesIO
    data = serialized
    
    import struct
    length = struct.unpack("!I", data[:4])[0]
    encrypted_data = data[4:]
    
    decrypted = enc.decrypt(encrypted_data)
    message_dict = __import__('json').loads(decrypted.decode('utf-8'))
    
    assert message_dict["type"] == "TEST"
    assert message_dict["payload"]["data"] == "secret"
