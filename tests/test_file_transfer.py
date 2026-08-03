import sys
import os
import tempfile
import threading
import time
import socket
import hashlib
import struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.DataTransferLayer.file_transfer import send_file, recv_file, SHA256Mismatch
from Core.DataTransferLayer.protocol import Message
from Core.DataTransferLayer.encryption import Encryption


def _send_raw_file(sock, filename, content, encryption=None, expected_sha256=None):
    sha = expected_sha256 if expected_sha256 is not None else hashlib.sha256(content).hexdigest()
    meta = Message("FILE_START", {"filename": filename, "size": len(content), "sha256": sha},
                   encrypted=True)
    sock.sendall(meta.serialize(encryption))
    chunk = encryption.encrypt(content) if encryption else content
    sock.sendall(struct.pack("!I", len(chunk)) + chunk)


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
        expected_sha256 = meta.payload.get("sha256")

        received_path = recv_file(conn, dest, filename, total_size, encryption=None,
                                  expected_sha256=expected_sha256)
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
        expected_sha256 = meta.payload.get("sha256")

        received_path = recv_file(conn, dest, filename, total_size, encryption=enc,
                                  expected_sha256=expected_sha256)
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


def test_file_transfer_wrong_hash_rejected():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(b"Payload data" * 50)
    tmp.flush()
    tmp.close()

    received_error = None
    rejected_path = None

    def server_task():
        nonlocal received_error, rejected_path
        conn, _ = server_socket.accept()
        conn.settimeout(10)
        dest = tempfile.mkdtemp()

        meta = Message.deserialize(conn, encryption=None)
        assert meta.type == "FILE_START"
        filename = meta.payload.get("filename")
        total_size = meta.payload.get("size")
        rejected_path = os.path.join(dest, filename)

        try:
            recv_file(conn, dest, filename, total_size, encryption=None,
                      expected_sha256="0" * 64)
        except SHA256Mismatch as e:
            received_error = e
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

    assert isinstance(received_error, SHA256Mismatch)
    assert rejected_path is not None
    assert not os.path.exists(rejected_path), "Plik z błędnym hashem musi zostać usunięty z dysku"

    os.unlink(tmp.name)


def test_progress_callback_send_and_recv():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]

    tmp = tempfile.NamedTemporaryFile(delete=False)
    content = b"progress payload " * 4000
    tmp.write(content)
    tmp.flush()
    tmp.close()

    send_progress = []
    recv_progress = []

    def server_task():
        conn, _ = server_socket.accept()
        conn.settimeout(10)
        dest = tempfile.mkdtemp()
        meta = Message.deserialize(conn, encryption=None)
        recv_file(conn, dest, meta.payload["filename"], meta.payload["size"],
                  encryption=None, expected_sha256=meta.payload["sha256"],
                  progress_callback=lambda s, t, v: recv_progress.append((s, t, v)))
        conn.close()

    server_thread = threading.Thread(target=server_task, daemon=True)
    server_thread.start()

    time.sleep(0.05)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    send_file(client, tmp.name, encryption=None,
              progress_callback=lambda s, t, v: send_progress.append((s, t, v)))
    client.close()

    server_thread.join(timeout=5)
    server_socket.close()
    os.unlink(tmp.name)

    for progress in (send_progress, recv_progress):
        assert progress, "progress_callback musi być wywołany"
        sent_vals = [p[0] for p in progress]
        total_vals = [p[1] for p in progress]
        assert sent_vals == sorted(sent_vals), "bytes_sent musi rosnąć monotonicznie"
        assert sent_vals[-1] == total_vals[-1] == len(content), \
            "Ostatni raport musi pokrywać pełny rozmiar pliku"
        assert all(p[2] >= 0 for p in progress), "Prędkość nie może być ujemna"


def test_recv_file_collision_keeps_both_files():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(2)
    port = server_socket.getsockname()[1]

    dest = tempfile.mkdtemp()
    content1 = b"first file content"
    content2 = b"second file content"
    saved = []

    def server_task():
        for _ in range(2):
            conn, _ = server_socket.accept()
            conn.settimeout(10)
            meta = Message.deserialize(conn, encryption=None)
            path = recv_file(conn, dest, meta.payload["filename"], meta.payload["size"],
                             encryption=None, expected_sha256=meta.payload["sha256"])
            saved.append(path)
            conn.close()

    server_thread = threading.Thread(target=server_task, daemon=True)
    server_thread.start()

    time.sleep(0.05)
    for content in (content1, content2):
        tmp_dir = tempfile.mkdtemp()
        tmp = os.path.join(tmp_dir, "photo.jpg")
        with open(tmp, "wb") as f:
            f.write(content)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_file(client, tmp, encryption=None)
        client.close()

    server_thread.join(timeout=5)
    server_socket.close()

    assert len(saved) == 2
    path1 = os.path.join(dest, "photo.jpg")
    path2 = os.path.join(dest, "photo_1.jpg")
    assert os.path.exists(path1), "Pierwszy plik musi istnieć"
    assert os.path.exists(path2), "Drugi plik musi istnieć z sufiksem _1"
    with open(path1, "rb") as f:
        assert f.read() == content1
    with open(path2, "rb") as f:
        assert f.read() == content2


def test_recv_file_path_traversal_sanitized():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]

    dest = tempfile.mkdtemp()
    content = b"not etc passwd"
    saved = []

    def server_task():
        conn, _ = server_socket.accept()
        conn.settimeout(10)
        meta = Message.deserialize(conn, encryption=None)
        path = recv_file(conn, dest, meta.payload["filename"], meta.payload["size"],
                         encryption=None, expected_sha256=meta.payload["sha256"])
        saved.append(path)
        conn.close()

    server_thread = threading.Thread(target=server_task, daemon=True)
    server_thread.start()

    time.sleep(0.05)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    _send_raw_file(client, "../../etc/passwd", content, encryption=None)
    client.close()

    server_thread.join(timeout=5)
    server_socket.close()

    assert len(saved) == 1
    assert saved[0] == os.path.join(dest, "passwd"), "Nazwa pliku musi być oczyszczona do basename"
    assert os.path.exists(os.path.join(dest, "passwd"))
    assert not os.path.exists(os.path.join(dest, "..", "etc", "passwd"))
    with open(os.path.join(dest, "passwd"), "rb") as f:
        assert f.read() == content
