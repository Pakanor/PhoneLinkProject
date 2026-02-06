import socket
import traceback
import os


def recv_all(sock, n):
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


def user_file_input(s, encryption):
    
    from Core.DataTransferLayer.file_transfer import send_file
    
    while True:
        file_path = input("Ścieżka do pliku (Enter = koniec): ").strip()
        
        if not file_path:
            print("[user_file_input] Koniec wysyłania plików")
            break
        
        if not os.path.exists(file_path):
            print(f"[user_file_input] ⚠️  Plik nie istnieje: {file_path}")
            continue
        
        if not os.path.isfile(file_path):
            print(f"[user_file_input] ⚠️  To nie jest plik: {file_path}")
            continue
        
        try:
            send_file(s, file_path, encryption)
            print(f"[user_file_input] ✓ Plik {file_path} wysłany pomyślnie")
        except Exception as e:
            print(f"[user_file_input] ❌ Błąd: {e}")
            traceback.print_exc()


