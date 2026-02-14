import os
import struct
import socket
from Core.DataTransferLayer.protocol import Message
from Core.ConnectionLayer.socket_utils import recv_all,ClientDisconnected
from Core.DataTransferLayer.encryption import Encryption


CHUNK_SIZE = 64 * 1024


def send_file(sock, filepath: str, encryption: Encryption = None, chunk_size: int = CHUNK_SIZE,send_metadata: bool = True):
    
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Plik nie istnieje: {filepath}")
        filename = os.path.basename(filepath)
        total_size = os.path.getsize(filepath)
        if send_metadata:
            meta = Message("FILE_START", {"filename": filename, "size": total_size}, encrypted=True)
            sock.sendall(meta.serialize(encryption))
            print(f"[send_file] Metadane wysłane")
        
        try:
            sock.getpeername()
        except (OSError, socket.error) as e:
            raise ConnectionError(f"Socket nie jest połączony: {e}")
        
        
        
        print(f"[send_file] Wysyłanie pliku: {filename} ({total_size} bajtów)")

       
        sent = 0
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
                    print(f"[send_file] Postęp: {sent}/{total_size} ({100*sent//total_size}%)")
                except OSError as e:
                    print(f"[send_file] Błąd wysyłania (socket zamknięty?): {e}")
                    raise ConnectionError(f"Nie można wysłać danych: {e}")
        
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




def recv_file(sock, dest_dir: str, filename: str, total_size: int, encryption: Encryption = None) -> str:
    
    try:
        print(f"[recv_file] Odbieranie pliku: {filename} ({total_size} bajtów)")

        dest_path = os.path.join(dest_dir, filename)
        os.makedirs(dest_dir, exist_ok=True)

        received = 0
        with open(dest_path, "wb") as f:
            while received < total_size:
                try:
                    length_bytes = recv_all(sock, 4)
                    chunk_len = struct.unpack("!I", length_bytes)[0]
                    
                    chunk_data = recv_all(sock, chunk_len)

                    if encryption:
                        try:
                            chunk = encryption.decrypt(chunk_data)
                        except Exception as e:
                            print(f"[recv_file] Błąd deszyfrowania: {e}, traktuję dane jako niezaszyfrowane")
                            chunk = chunk_data
                    else:
                        chunk = chunk_data

                    f.write(chunk)
                    received += len(chunk)
                    print(f"[recv_file] Postęp: {received}/{total_size} ({100*received//total_size}%)")
                    
                except OSError as e:
                    print(f"[recv_file] Błąd OS (socket zamknięty?): {e}")
                    raise ConnectionError(f"Połączenie przerwane: {e}")
                except ClientDisconnected:
                    print("Klient rozłączył się.")
                    sock.close()
                    return
                except Exception as e:
                    print(f"[recv_file] Nieoczekiwany błąd: {e}")
                    raise

        print(f"[recv_file] Plik {filename} całkowicie odebrany")
        return dest_path
        
    except Exception as e:
        print(f"[recv_file] Fatalny błąd: {e}")
        raise
