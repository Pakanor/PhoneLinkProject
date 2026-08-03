import socket
import threading
import time
import sys
import os
import queue as queue_mod
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.ConnectionLayer.tcpServer import tcpServer
from Core.DataTransferLayer.handshake import HandshakeManager


def _drain(q):
    events = []
    while True:
        try:
            events.append(q.get_nowait())
        except queue_mod.Empty:
            break
    return events


def _wait_until(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_event_queue_receives_connection_events():
    event_queue = queue_mod.Queue()
    server = tcpServer("127.0.0.1", 0, event_queue=event_queue)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()

    assert _wait_until(lambda: server.port != 0), "Serwer nie wystartował"

    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.settimeout(10)
    s1.connect(("127.0.0.1", server.port))
    HandshakeManager.client_handshake(s1)

    assert _wait_until(lambda: len(server.get_client_ids()) == 1), \
        "Klient musi zostać zarejestrowany"
    connected_types = {t for t, _ in _drain(event_queue)}
    assert "client_connected" in connected_types
    assert "log" in connected_types

    s1.close()
    assert _wait_until(lambda: len(server.get_client_ids()) == 0), \
        "Klient musi zostać wyrejestrowany"
    disconnected_types = {t for t, _ in _drain(event_queue)}
    assert "client_disconnected" in disconnected_types

    server.stop()


def test_multiple_clients_do_not_disconnect_each_other():
    server = tcpServer("127.0.0.1", 0)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()

    assert _wait_until(lambda: server.port != 0), "Serwer nie wystartował"

    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.settimeout(10)
    s1.connect(("127.0.0.1", server.port))
    HandshakeManager.client_handshake(s1)

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(10)
    s2.connect(("127.0.0.1", server.port))
    HandshakeManager.client_handshake(s2)

    assert _wait_until(lambda: len(server.get_client_ids()) == 2), \
        "Oba połączenia muszą być zarejestrowane"
    ids_before = set(server.get_client_ids())
    assert len(ids_before) == 2

    s1.close()
    assert _wait_until(lambda: len(server.get_client_ids()) == 1), \
        "Odłączenie pierwszego klienta musi usunąć tylko jego sesję"
    remaining = set(server.get_client_ids())
    assert len(remaining) == 1, "Drugi klient musi pozostać zarejestrowany"
    assert remaining.issubset(ids_before)

    server.stop()
    s2.close()


def test_stop_disconnects_all_clients():
    server = tcpServer("127.0.0.1", 0)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()

    assert _wait_until(lambda: server.port != 0), "Serwer nie wystartował"

    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.settimeout(10)
    s1.connect(("127.0.0.1", server.port))
    HandshakeManager.client_handshake(s1)

    assert _wait_until(lambda: len(server.get_client_ids()) == 1)
    server.stop()

    assert _wait_until(lambda: len(server.get_client_ids()) == 0), \
        "Po stop() rejestr klientów musi być pusty"

    data = s1.recv(1024)
    assert data == b"", "Socket klienta musi być zamknięty po stop()"
    s1.close()
