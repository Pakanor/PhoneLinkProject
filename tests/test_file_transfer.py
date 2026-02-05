import sys
import os
import tempfile
import threading
import time
import socket
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.DataTransferLayer.file_transfer import send_file, recv_file
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.encryption import Encryption


def test_file_transfer_plain():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(b"Test file content" * 100)
    tmp.flush()
    tmp.close()

    received_path = None

    def server_task():
        nonlocal received_path
        conn, _ = server_socket.accept()
        conn.settimeout(10)
        dest = tempfile.mkdtemp()
        
        meta = Message.deserialize(conn, encryption=None)
        assert meta.type == "FILE_START"
        filename = meta.payload.get("filename")
        total_size = meta.payload.get("size")
        
        received_path = recv_file(conn, dest, filename, total_size, encryption=None)
        conn.close()

    server_thread = threading.Thread(target=server_task, daemon=True)
    server_thread.start()

    time.sleep(0.05)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    send_file(client, tmp.name, encryption=None)
    client.close()

    server_thread.join(timeout=5)
    server_socket.close()

    assert received_path is not None
    with open(tmp.name, "rb") as a, open(received_path, "rb") as b:
        assert a.read() == b.read()

    os.unlink(tmp.name)


def test_file_transfer_encrypted():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]

    tmp = tempfile.NamedTemporaryFile(delete=False)
    content = b"Secret content" * 500
    tmp.write(content)
    tmp.flush()
    tmp.close()

    enc = Encryption()  
    received_path = None

    def server_task():
        nonlocal received_path
        conn, _ = server_socket.accept()
        conn.settimeout(10)
        dest = tempfile.mkdtemp()
        
        meta = Message.deserialize(conn, encryption=enc)
        assert meta.type == "FILE_START"
        filename = meta.payload.get("filename")
        total_size = meta.payload.get("size")
        
        received_path = recv_file(conn, dest, filename, total_size, encryption=enc)
        conn.close()

    server_thread = threading.Thread(target=server_task, daemon=True)
    server_thread.start()

    time.sleep(0.05)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    send_file(client, tmp.name, encryption=enc)
    client.close()

    server_thread.join(timeout=5)
    server_socket.close()

    assert received_path is not None
    with open(tmp.name, "rb") as a, open(received_path, "rb") as b:
        assert a.read() == b.read()

    os.unlink(tmp.name)
