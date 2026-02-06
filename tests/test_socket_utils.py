import pytest
import socket
import threading
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.ConnectionLayer.socket_utils import recv_all


def test_recv_all_small_data():
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]
    
    def send_data():
        time.sleep(0.1)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        client.sendall(b"Hello World")
        client.close()
    
    client_thread = threading.Thread(target=send_data, daemon=True)
    client_thread.start()
    
    conn, _ = server_socket.accept()
    conn.settimeout(5)
    
    data = recv_all(conn, 11)  
    
    assert data == b"Hello World"
    
    client_thread.join(timeout=5)
    conn.close()
    server_socket.close()


def test_recv_all_large_data():
    
    large_data = b"X" * (1024 * 1024 + 500)  
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]
    
    def send_large_data():
        time.sleep(0.1)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        client.sendall(large_data)
        client.close()
    
    client_thread = threading.Thread(target=send_large_data, daemon=True)
    client_thread.start()
    
    conn, _ = server_socket.accept()
    conn.settimeout(10)
    
    data = recv_all(conn, len(large_data))
    
    assert len(data) == len(large_data)
    assert data == large_data
    
    client_thread.join(timeout=10)
    conn.close()
    server_socket.close()


def test_recv_all_timeout():
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    
    conn, _ = server_socket.accept()
    conn.settimeout(0.5)
    
    client.sendall(b"Hello")
    
    with pytest.raises(ConnectionError):
        recv_all(conn, 100)
    
    client.close()
    conn.close()
    server_socket.close()


def test_recv_all_connection_closed():
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    port = server_socket.getsockname()[1]
    
    def close_connection():
        time.sleep(0.1)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        client.close()
    
    client_thread = threading.Thread(target=close_connection, daemon=True)
    client_thread.start()
    
    conn, _ = server_socket.accept()
    conn.settimeout(5)
    
    with pytest.raises(ConnectionError):
        recv_all(conn, 1000)
    
    client_thread.join(timeout=5)
    conn.close()
    server_socket.close()
