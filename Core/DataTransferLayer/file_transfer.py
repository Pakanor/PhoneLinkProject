import os
import struct
import socket
import hashlib
import time
from Core.DataTransferLayer.protocol import Message
from Core.ConnectionLayer.socket_utils import recv_all, ClientDisconnected
from Core.DataTransferLayer.encryption import Encryption


CHUNK_SIZE = 64 * 1024


class ProgressTracker:
    def __init__(self, callback, total_bytes):
        self.callback = callback
        self.total = total_bytes
        self._start = time.monotonic()
        self._last_time = self._start
        self._last_bytes = 0
        self._ema_speed = None

    def update(self, current):
        now = time.monotonic()
        dt = now - self._last_time
        if dt < 0.1 and current < self.total:
            return
        if dt > 0:
            speed = (current - self._last_bytes) / dt / 1_000_000
        else:
            speed = 0.0
        if speed > 0:
            if self._ema_speed is None:
                self._ema_speed = speed
            else:
                self._ema_speed = 0.7 * self._ema_speed + 0.3 * speed
        self._last_time = now
        self._last_bytes = current
        if self.callback:
            self.callback(current, self.total, self._ema_speed if self._ema_speed else 0.0)


class SHA256Mismatch(Exception):
    pass


def _file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_remove(filepath: str):
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError as e:
        print(f"[recv_file] Błąd usuwania pliku {filepath}: {e}")


def sanitize_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename:
        raise ValueError("Nieprawidłowa nazwa pliku")
    name = os.path.basename(filename.replace("\\", "/"))
    if not name or name in (".", ".."):
        raise ValueError("Nieprawidłowa nazwa pliku")
    if "\x00" in name:
        raise ValueError("Nieprawidłowa nazwa pliku")
    return name


def _open_unique_file(dest_dir: str, filename: str):
    base, ext = os.path.splitext(filename)
    path = os.path.join(dest_dir, filename)
    try:
        return path, open(path, "xb")
    except FileExistsError:
        pass
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        path = os.path.join(dest_dir, candidate)
        try:
            return path, open(path, "xb")
        except FileExistsError:
            counter += 1


def send_file(sock, filepath: str, encryption: Encryption = None, chunk_size: int = CHUNK_SIZE,
              send_metadata: bool = True, progress_callback=None):
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Plik nie istnieje: {filepath}")
        filename = os.path.basename(filepath)
        total_size = os.path.getsize(filepath)
        if send_metadata:
            meta = Message(
                "FILE_START",
                {"filename": filename, "size": total_size, "sha256": _file_sha256(filepath)},
                encrypted=True
            )
            sock.sendall(meta.serialize(encryption))
            print(f"[send_file] Metadane wysłane")

        try:
            sock.getpeername()
        except (OSError, socket.error) as e:
            raise ConnectionError(f"Socket nie jest połączony: {e}")

        print(f"[send_file] Wysyłanie pliku: {filename} ({total_size} bajtów)")

        sent = 0
        tracker = ProgressTracker(progress_callback, total_size)
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                if encryption:
                    chunk_to_send = encryption.encrypt(chunk)
                else:
                    chunk_to_send = chunk

                try:
                    sock.sendall(struct.pack("!I", len(chunk_to_send)))
                    sock.sendall(chunk_to_send)
                    sent += len(chunk)
                    tracker.update(sent)
                    print(f"[send_file] Postęp: {sent}/{total_size} ({100*sent//total_size}%)")
                except OSError as e:
                    print(f"[send_file] Błąd wysyłania (socket zamknięty?): {e}")
                    raise ConnectionError(f"Nie można wysłać danych: {e}")

        tracker.update(sent)
        print(f"[send_file] Plik {filename} całkowicie wysłany")

    except FileNotFoundError as e:
        print(f"[send_file] Błąd: {e}")
        raise
    except ConnectionError as e:
        print(f"[send_file] Błąd połączenia: {e}")
        raise
    except OSError as e:
        print(f"[send_file] Błąd OS: {e}")
        raise
    except Exception as e:
        print(f"[send_file] Nieoczekiwany błąd: {e}")
        raise


def recv_file(sock, dest_dir: str, filename: str, total_size: int,
              encryption: Encryption = None, expected_sha256: str = None,
              progress_callback=None) -> str:
    name = sanitize_filename(filename)
    os.makedirs(dest_dir, exist_ok=True)
    print(f"[recv_file] Odbieranie pliku: {name} ({total_size} bajtów)")

    dest_path, file_obj = _open_unique_file(dest_dir, name)

    hasher = hashlib.sha256()
    received = 0
    tracker = ProgressTracker(progress_callback, total_size)
    try:
        with file_obj:
            while received < total_size:
                length_bytes = recv_all(sock, 4)
                chunk_len = struct.unpack("!I", length_bytes)[0]

                chunk_data = recv_all(sock, chunk_len)

                if encryption:
                    chunk = encryption.decrypt(chunk_data)
                else:
                    chunk = chunk_data

                file_obj.write(chunk)
                hasher.update(chunk)
                received += len(chunk)
                tracker.update(received)
                print(f"[recv_file] Postęp: {received}/{total_size} ({100*received//total_size}%)")
    except ClientDisconnected:
        print("[recv_file] Klient rozłączył się podczas transferu, usuwam niekompletny plik")
        _safe_remove(dest_path)
        raise
    except Exception as e:
        print(f"[recv_file] Błąd podczas transferu, usuwam niekompletny plik: {e}")
        _safe_remove(dest_path)
        raise

    if expected_sha256:
        computed = hasher.hexdigest()
        if computed != expected_sha256:
            print(f"[recv_file] SHA-256 mismatch! Oczekiwano {expected_sha256}, otrzymano {computed}")
            _safe_remove(dest_path)
            raise SHA256Mismatch("SHA-256 mismatch")

    tracker.update(received)
    print(f"[recv_file] Plik {name} całkowicie odebrany")
    return dest_path
