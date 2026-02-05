import socket

class socket_utils:
    @staticmethod
    def recv_all(sock, n):
        """Odbiera dokładnie n bajtów z socketa"""
        data = b""
        while len(data) < n:
            try:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    raise ConnectionError(f"Połączenie przerwane. Oczekiwano {n} bajtów, otrzymano {len(data)}")
                data += chunk
            except socket.timeout:
                raise ConnectionError(f"Timeout: oczekiwano {n} bajtów, otrzymano {len(data)}")
        return data


