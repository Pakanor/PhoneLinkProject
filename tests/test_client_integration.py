import socket
import threading
import time
import sys
import os
import tempfile
import hashlib
import uuid
import queue as queue_mod
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeroconf import Zeroconf, ServiceInfo

from Core.ConnectionLayer import socket_utils
from Core.ConnectionLayer.tcpServer import tcpServer
from Core.ConnectionLayer.client_discovery import ServerDiscovery
from phone_client import PhoneClient


def _file_sha256(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _wait_until(predicate, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _register_service(port, name=None):
    if name is None:
        name = f"PhoneLink-Test-{uuid.uuid4().hex[:8]}._phonelink._tcp.local."
    zeroconf = Zeroconf()
    info = ServiceInfo(
        "_phonelink._tcp.local.",
        name,
        addresses=[socket.inet_aton("127.0.0.1")],
        port=port,
        properties={}
    )
    zeroconf.register_service(info)
    return zeroconf, info


def test_server_discovery_finds_registered_service():
    name = f"PhoneLink-Test-{uuid.uuid4().hex[:8]}._phonelink._tcp.local."
    zeroconf, info = _register_service(54321, name)
    try:
        host, port = ServerDiscovery(timeout=8.0, service_name=name).find_server()
        assert host == "127.0.0.1"
        assert port == 54321
    finally:
        zeroconf.unregister_service(info)
        zeroconf.close()


def test_full_client_integration_cycle():
    received_dir = tempfile.mkdtemp()
    socket_utils.BASE_DIR = received_dir

    server = tcpServer("127.0.0.1", 0)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    assert _wait_until(lambda: server.port != 0), "Serwer nie wystartował"

    name = f"PhoneLink-Test-{uuid.uuid4().hex[:8]}._phonelink._tcp.local."
    zeroconf, info = _register_service(server.port, name)

    try:
        try:
            host, port = ServerDiscovery(timeout=5.0, service_name=name).find_server()
        except TimeoutError:
            host, port = "127.0.0.1", server.port

        src_dir = tempfile.mkdtemp()
        client_file = os.path.join(src_dir, "doc1.txt")
        content1 = b"client to server payload " * 200
        with open(client_file, "wb") as f:
            f.write(content1)

        server_file = os.path.join(src_dir, "doc2.bin")
        content2 = bytes(range(256)) * 40
        with open(server_file, "wb") as f:
            f.write(content2)

        client = PhoneClient(host, port)
        try:
            client.connect()
            client.start_listener()

            assert _wait_until(lambda: len(server.get_client_ids()) == 1), \
                "Klient nie zarejestrowany na serwerze"

            cid = server.get_client_ids()[0]
            server.send_file_to_client(server_file, client_id=cid)
            client_dest = os.path.join(received_dir, "from_server", os.path.basename(server_file))
            assert _wait_until(lambda: os.path.exists(client_dest)), \
                "Plik serwer -> klient nie dotarł"
            assert _file_sha256(client_dest) == _file_sha256(server_file), \
                "SHA-256 pliku odebranego przez klienta jest błędne"

            assert client.send_file(client_file) is True
            server_dest = os.path.join(received_dir, "from_clients", os.path.basename(client_file))
            assert _wait_until(lambda: os.path.exists(server_dest)), \
                "Plik klient -> serwer nie dotarł"
            assert _file_sha256(server_dest) == _file_sha256(client_file), \
                "SHA-256 pliku odebranego przez serwer jest błędne"
        finally:
            client.close()
            server.stop()

        assert _wait_until(lambda: len(server.get_client_ids()) == 0), \
            "Rejestr klientów musi być pusty po rozłączeniu"
    finally:
        zeroconf.unregister_service(info)
        zeroconf.close()


def _drain(q):
    events = []
    while True:
        try:
            events.append(q.get_nowait())
        except queue_mod.Empty:
            break
    return events


def _wait_for_event(q, predicate, timeout=8.0):
    deadline = time.time() + timeout
    events = []
    while time.time() < deadline:
        events += _drain(q)
        if any(predicate(e) for e in events):
            return events
        time.sleep(0.05)
    return events


def test_server_emits_transfer_events():
    received_dir = tempfile.mkdtemp()
    socket_utils.BASE_DIR = received_dir
    event_queue = queue_mod.Queue()

    server = tcpServer("127.0.0.1", 0, event_queue=event_queue)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    assert _wait_until(lambda: server.port != 0), "Serwer nie wystartował"

    src_dir = tempfile.mkdtemp()
    src_file = os.path.join(src_dir, "big.bin")
    with open(src_file, "wb") as f:
        f.write(b"X" * (1024 * 512))

    client = PhoneClient("127.0.0.1", server.port)
    try:
        client.connect()
        client.start_listener()
        assert _wait_until(lambda: len(server.get_client_ids()) == 1)
        cid = server.get_client_ids()[0]

        progress = []

        assert client.send_file(src_file) is True
        server_dest = os.path.join(received_dir, "from_clients", "big.bin")
        progress += _wait_for_event(
            event_queue,
            lambda e: e[0] == "transfer_complete"
            and e[1].get("direction") == "recv" and e[1].get("ok") is True)
        assert os.path.exists(server_dest)
        done = [d for t, d in progress if t == "transfer_complete"]
        assert any(d["direction"] == "recv" and d["ok"] is True for d in done)
        assert any("SHA-256 OK" in d["message"] for t, d in progress if t == "log")

        server.send_file_to_client(src_file, client_id=cid)
        client_dest = os.path.join(received_dir, "from_server", "big.bin")
        progress += _wait_for_event(
            event_queue,
            lambda e: e[0] == "transfer_complete"
            and e[1].get("direction") == "send" and e[1].get("ok") is True)
        assert os.path.exists(client_dest)

        progress_types = {t for t, _ in progress}
        assert "transfer_progress" in progress_types
        assert "transfer_complete" in progress_types
        done = [d for t, d in progress if t == "transfer_complete"]
        assert done and done[-1]["ok"] is True and done[-1]["direction"] == "send"
    finally:
        client.close()
        server.stop()
