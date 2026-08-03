# PhoneLink – pełna dokumentacja projektu

## 1. Ogólny opis projektu

**PhoneLink** to aplikacja do bezprzewodowej (sieć lokalna) wymiany plików typu **peer-to-peer (P2P)** między komputerem (serwer, laptop) a telefonem (klient). Projekt jest napisany w języku **Python 3** i opiera się na:

- **TCP socketach** jako warstwie transportowej (bez użycia HTTP),
- **szyfrowaniu AES-256-GCM** (`cryptography` / `AESGCM`) dla całej komunikacji po wymianie klucza,
- **Zeroconf (mDNS)** do automatycznego wykrywania serwera przez telefon w sieci lokalnej (bez wpisywania adresu IP ręcznie),
- **Tkinter + tkinterdnd2** jako graficznym interfejsie użytkownika (GUI) po stronie komputera z obsługą *drag & drop*,
- **własnym binarnym protokołem** na bazie prefiksów długości (length-prefixed JSON).

Autor projektu: Robert. Projekt jest na wczesnym etapie (prototyp/MVP). Główny katalog: `/home/roberto/Projects/PhoneLink`.

---

## 2. Struktura repozytorium

```
PhoneLink/
├── main.py                                  # punkt wejścia: serwer + GUI (strona komputera)
├── Core/
│   ├── ConnectionLayer/                     # warstwa połączeniowa / sieciowa
│   │   ├── registerService.py               # rejestracja usługi w Zeroconf + pobranie lokalnego IP
│   │   ├── socket_utils.py                  # recv_all + handler'y wiadomości serwera i klienta
│   │   └── tcpServer.py                     # serwer TCP, obsługa klienta, wysyłanie pliku do klienta
│   └── DataTransferLayer/                   # warstwa danych
│       ├── encryption.py                    # klasa Encryption (AES-256-GCM, klucze, PBKDF2)
│       ├── file_transfer.py                 # send_file() / recv_file() – przesyłanie plików w chunkach
│       ├── handshake.py                     # HandshakeManager – wymiana klucza (uzgadnianie połączenia)
│       └── protocol.py                      # klasa Message – ramka wiadomości (serializacja/deserializacja)
├── UiLayer/
│   └── gui.py                               # P2PGUI – okno Tkinter z drag & drop
├── tests/                                   # testy pytest
│   ├── __init__.py                          # (pusty)
│   ├── test_encryption.py
│   ├── test_file_transfer.py
│   ├── test_handshake.py
│   └── test_socket_utils.py
├── .github/workflows/python-tests.yml       # CI/CD: GitHub Actions (testy + lint)
├── requirements.txt                         # zależności produkcyjne (pinned)
├── requirements-dev.txt                     # zależności deweloperskie
├── pytest.ini                               # konfiguracja pytest
├── .flake8                                  # konfiguracja flake8
├── .gitignore
├── run_tests.sh                             # skrypt uruchamiający testy z pokryciem
├── venv/                                    # wirtualne środowisko (nie w repo)
└── opis.md                                  # ten dokument
```

**Uwaga:** w repozytorium **nie ma już pliku `phone.py`** (strona klienta/telefonu) – został **usunięty** w ostatnim commicie „code reduction" (2026-02-17). Obecnie w repo istnieje wyłącznie strona serwerowa + GUI. Dawny `phone.py` jest nadal dostępny w historii gita i pełnił rolę klienta (patrz sekcja 13).

---

## 3. Warstwy i odpowiedzialności

| Warstwa | Katalog | Rola |
|---|---|---|
| Warstwa połączeniowa | `Core/ConnectionLayer/` | TCP, przyjmowanie/wysyłanie, rejestracja usługi, obsługa zdarzeń sieci |
| Warstwa danych | `Core/DataTransferLayer/` | szyfrowanie, handshake, protokół wiadomości, transfer plików |
| Warstwa UI | `UiLayer/` | interfejs graficzny (Tkinter) |
| Testy | `tests/` | testy jednostkowe i integracyjne |

---

## 4. Przepływ działania programu (krok po kroku)

### 4.1 Start aplikacji (komputer) – `main.py`

1. `service = RegisterService()` – tworzona jest instancja rejestratora usługi.
2. `HOST = service.get_local_ip()` – pobierany jest lokalny adres IP komputera.
3. `PORT = 5000` – twardo zakodowany port nasłuchu.
4. `server = tcpServer(HOST, PORT)` – tworzony jest serwer TCP.
5. `server_thread = threading.Thread(target=server.start, daemon=True)` – serwer startuje w **wątku demonicznym** (daemon), więc nie blokuje zamykania programu.
6. `service.connect()` – rejestracja usługi w Zeroconf (mDNS), aby telefon mógł znaleźć komputer (uwaga: funkcja blokuje wątek główny na **5 sekund** – `time.sleep(5)`).
7. Definiowany jest callback `on_file_selected(filepath)`:
   - tworzy nowy **wątek nieterminowy** (daemon=False) z targetem `server.send_file_to_client(filepath)`,
   - dodaje wątek do listy `active_transfers`,
   - startuje wątek.
8. `gui = P2PGUI(on_file_selected_callback=on_file_selected)` – tworzone jest okno GUI.
9. `gui.run()` – start pętli zdarzeń Tkinter (`mainloop()`). Program działa tutaj do zamknięcia okna.
10. Po zamknięciu okna: pętla czeka na zakończenie aktywnych transferów `t.join(timeout=10)` (maks. 10 s na wątek), a na końcu `server.stop()` zatrzymuje serwer.

**Model wątków:**
- wątek główny → GUI (Tkinter),
- wątek demoniczny → serwer TCP (`server.start`),
- wątek nieterminowy na każdy wysyłany plik (transfer server→client).

### 4.2 Uruchomienie serwera TCP – `tcpServer.start()`

1. `self.running = True`.
2. Otwiera gniazdo `socket.socket(socket.AF_INET, socket.SOCK_STREAM)` w bloku `with` (zamknie się przy błędzie).
3. `s.bind((host, port))`, `s.listen()`.
4. Pętla `while self.running:`:
   - `conn, addr = s.accept()` – czeka na połączenie przychodzące,
   - `conn.settimeout(3600)` – **timeout 1 godzina** na socket,
   - tworzy nowy wątek `handle_client(conn)` i startuje go (wielowątkowa obsługa),
   - przy wyjątku ustawia `self.running = False` i przerywa pętlę.
5. `conn.close()` – po wyjściu z pętli (uwaga: odnosi się do ostatnio zaakceptowanego `conn`).

### 4.3 Obsługa klienta – `tcpServer.handle_client(conn)`

1. `encryption = HandshakeManager.server_handshake(conn)` – wymiana klucza (patrz sekcja 6).
2. `self.client = (conn, encryption)` – zapisuje parę (socket, klucz) jako „podłączony klient". **Uwaga: serwer trzyma tylko JEDNEGO klienta naraz** – nowe połączenie nadpisze poprzednie.
3. Pętla nieskończona:
   - `Message.deserialize(conn, encryption)` – czeka na wiadomość,
   - `server_handle_message(received_msg, conn, encryption)` – obsługuje wiadomość,
   - przy wyjątku: wypisuje błąd i **przerywa pętlę**.
4. W `finally:` wywoływane jest `self.remove_client()` – zamyka socket klienta i zeruje `self.client`.

### 4.4 Wysyłanie pliku z serwera do klienta – `tcpServer.send_file_to_client(file_path, mode="server")`

1. Jeśli plik nie istnieje → komunikat i `return`.
2. Jeśli brak klienta (`self.client` jest `None`) → komunikat i `return`.
3. `conn, encryption = self.client`.
4. `file_size = os.path.getsize(file_path)`, `filename = os.path.basename(file_path)`.
5. Wysyła wiadomość `FILE_START` z payload `{"filename": ..., "size": ...}` (zaszyfrowaną).
6. `send_file(conn, file_path, encryption, send_metadata=False)` – wysyła zawartość pliku w chunkach **bez ponownego wysyłania metadanych** (bo `FILE_START` już poszedł).
7. Wyjątki są łapane i drukowane (z tracebackiem) – transfer nie kończy się błędem krytycznym.

### 4.5 Strona klienta (telefon) – dawny `phone.py`

Klient działał następująco:
1. `zeroconf = Zeroconf()` + `ServiceBrowser(zeroconf, "_phonelink._tcp.local.", phone)` – **skanowanie sieci** w poszukiwaniu usługi PhoneLink.
2. Callback `phone.add_service(...)` – po znalezieniu usługi pobiera jej IP i port oraz ustawia `found_event`.
3. `phone.found_event.wait()` – blokuje do znalezienia serwera. Potem `zeroconf.close()`.
4. `socket.socket(...)` + `connect((phone.ip, phone.port))` – połączenie TCP.
5. `HandshakeManager.client_handshake(s)` – wymiana klucza (patrz sekcja 6).
6. Wysyła `GREETING` `{"user": "telefon", "action": "connect"}`.
7. Odbiera odpowiedź `GREETING_ACK`.
8. Startuje wątek nasłuchujący `listen_server` (pętla: `Message.deserialize` → `client_handle_message`), który odbiera m.in. nadchodzące pliki.
9. `user_file_input(s, encryption)` – interaktywne wysyłanie pliku przez konsolę (usunięte w ostatnim refaktorze).

### 4.6 Obsługa wiadomości – `socket_utils.py`

`server_handle_message(received_msg, conn, encryption)`:
- **`GREETING`** → wysyła `GREETING_ACK` `{"status": "OK"}` (zaszyfrowane).
- **`FILE_START`** → czyta `filename` i `size` z payload, tworzy katalog docelowy, woła `recv_file(...)`, po zapisaniu wysyła `FILE_ACK` `{"status": "OK", "saved_path": ...}`.
- **`FILE_ACK`** → tylko loguje potwierdzenie otrzymania pliku.
- **inne typy** → wysyła `ERROR` `{"error": "Unknown message type"}`.

`client_handle_message(received_msg, conn, encryption)` (strona klienta):
- **`GREETING_ACK`** → log „Serwer przywitał się OK".
- **`FILE_START`** → odbiera plik do `~/PhoneLink_received/from_server/`, wysyła `FILE_ACK` z zapisaną ścieżką.
- **`FILE_ACK`** → log „Transfer zakończony".
- **`ERROR`** → log błędu.
- **inne** → log „Nieznany typ".

---

## 5. Protokół sieciowy – `protocol.py`

### 5.1 Format ramki wiadomości (Message)

Każda wiadomość przesyłana po TCP składa się z:

```
[4 bajty długości (big-endian, struct "!I")] [payload (JSON, opcjonalnie zaszyfrowany)]
```

- Prefiks długości to `struct.pack("!I", len(json_data))`.
- Payload to JSON: `{"type": "<TYP>", "payload": {<dane>}}` zakodowany jako UTF-8.
- Jeśli wiadomość ma `encrypted=True` **oraz** podany jest obiekt `encryption`, to **cały JSON jest szyfrowany** przed dodaniem prefiksu długości (szyfrowana jest cała ramka JSON, nie sam payload).

### 5.2 Klasyfikacja szyfrowania wiadomości

- **Handshake (HANDSHAKE, HANDSHAKE_ACK)** – wysyłane **jawnie (plaintext)**, bez szyfrowania, bo klucz jeszcze nie istnieje.
- **Wszystkie wiadomości po handshake (HANDSHAKE_DONE, GREETING, GREETING_ACK, FILE_START, FILE_ACK, ERROR)** – `encrypted=True`, szyfrowane kluczem uzgodnionym w handshake.

### 5.3 Typy wiadomości (rejestr)

| Typ | Kierunek | Payload | Uwagi |
|---|---|---|---|
| `HANDSHAKE` | client → server | `{"version": "1.0", "supported_ciphers": ["AES-256-GCM"]}` | plaintext |
| `HANDSHAKE_ACK` | server → client | `{"cipher_selected": "AES-256-GCM", "server_key": <base64>}` | plaintext |
| `HANDSHAKE_DONE` | client → server | `{"status": "OK"}` | szyfrowane |
| `GREETING` | client → server | `{"user": ..., "action": "connect"}` | szyfrowane |
| `GREETING_ACK` | server → client | `{"status": "OK"}` | szyfrowane |
| `FILE_START` | obie strony | `{"filename": ..., "size": ...}` | szyfrowane |
| `FILE_ACK` | obie strony | `{"status": "OK", "saved_path": ...}` | szyfrowane |
| `ERROR` | obie strony | `{"error": ...}` | szyfrowane |

### 5.4 Deserializacja

`Message.deserialize(sock, encryption=None)`:
1. Czyta 4 bajty długości (`recv_all`).
2. Rozpakowuje długość (`!I`).
3. Czyta dokładnie `message_length` bajtów.
4. Jeśli `encryption` podany → próbuje odszyfrować. **Przy błędzie deszyfrowania wiadomość NIE jest odrzucana – jest traktowana jako niezaszyfrowana** (fallback, patrz sekcja 12 – to słabość bezpieczeństwa).
5. Dekoduje UTF-8, parsuje JSON, zwraca `Message(type, payload, encrypted=encryption is not None)`.

---

## 6. Handshake (wymiana klucza) – `handshake.py`

`HandshakeManager`:
- `PROTOCOL_VERSION = "1.0"`
- `SUPPORTED_CIPHERS = ["AES-256-GCM"]`

### 6.1 Strona serwera – `server_handshake(sock)`

1. Odbiera `HANDSHAKE` (plaintext). Jeśli typ ≠ `HANDSHAKE` → wyjątek.
2. **Generuje nowy klucz AES-256**: `encryption = Encryption()` (klucz losowy 32 bajty).
3. Wysyła `HANDSHAKE_ACK` (plaintext) z `{"cipher_selected": "AES-256-GCM", "server_key": <klucz w base64>}`.
4. Próbuje odebrać `HANDSHAKE_DONE` (już zaszyfrowane kluczem). Jeśli się nie uda lub typ jest inny – tylko loguje ostrzeżenie, **nie przerywa**.
5. Zwraca obiekt `encryption` (klucz pozostaje u serwera).

### 6.2 Strona klienta – `client_handshake(sock)`

1. Wysyła `HANDSHAKE` z wersją protokołu i listą obsługiwanych szyfrów (plaintext).
2. Odbiera `HANDSHAKE_ACK`. Jeśli typ ≠ `HANDSHAKE_ACK` → wyjątek.
3. Pobiera `cipher_selected` i `server_key` (base64) z payload.
4. Tworzy `Encryption.from_b64(server_key_b64)` – **klient używa klucza wygenerowanego przez serwer**.
5. Wysyła `HANDSHAKE_DONE` (zaszyfrowane kluczem).
6. Zwraca `encryption`.

**Konsekwencja:** to NIE jest bezpieczny protokół uzgadniania kluczy (brak Diffiego-Hellmana, brak podpisu/asymetrii). Klucz jest generowany przez serwer i wysyłany **w postaci jawnej (base64)** w wiadomości `HANDSHAKE_ACK`. Każdy podsłuchujący w sieci może przechwycić klucz i odszyfrować całą komunikację (podatność na MITM / sniffing).

---

## 7. Szyfrowanie – `encryption.py`

Klasa `Encryption`:
- `CIPHER_SUITE = "AES-256-GCM"`
- `KEY_SIZE = 32` (256 bitów)
- `NONCE_SIZE = 12` bajtów
- `TAG_SIZE = 16` bajtów (tag autentykacji GCM – dołączany automatycznie przez `cryptography`)

### 7.1 Metody

- `__init__(shared_key=None)` – jeśli brak klucza, generuje losowy 32-bajtowy (`os.urandom`). Jeśli podany, wymusza `len == 32` (assert).
- `generate_key()` (static) – losowy klucz 32 B.
- `derive_key(password, salt=None)` (static) – **PBKDF2-HMAC-SHA256**, 100 000 iteracji, długość 32 B, losowa sól 16 B (zwraca `(klucz, sól)`). W razie braku `cryptography.kdf` fallback do `os.urandom`. **Uwaga:** obecnie metoda nie jest używana w głównym przepływie (możliwość przyszłego hasła/klucza opartego o hasło).
- `encrypt(plaintext) -> bytes` – losowy nonce 12 B, `AESGCM.encrypt(nonce, plaintext, None)` (AAD = None), zwraca **`nonce + ciphertext`** (nonce na początku).
- `decrypt(encrypted_data) -> bytes` – odcina pierwsze 12 B (nonce), reszta to ciphertext+tag, `AESGCM.decrypt(...)`.
- `get_key_b64() -> str` – klucz w base64.
- `from_b64(key_b64)` (static) – tworzy `Encryption` z klucza base64.

**Ważne:** szyfrowanie używane jest zarówno do całych wiadomości (`Message`), jak i do każdego chunku pliku z osobna (każdy chunk ma **własny, nowy nonce**).

---

## 8. Transfer plików – `file_transfer.py`

Stała: `CHUNK_SIZE = 64 * 1024` (64 KB).

### 8.1 `send_file(sock, filepath, encryption=None, chunk_size=CHUNK_SIZE, send_metadata=True)`

1. Sprawdza, czy plik istnieje (`FileNotFoundError`).
2. `filename = basename`, `total_size = getsize`.
3. Jeśli `send_metadata=True` → wysyła `FILE_START` z `{"filename", "size"}` (zaszyfrowany). (W `send_file_to_client` serwera jest `False`, bo `FILE_START` wysyłany jest wcześniej ręcznie.)
4. Sprawdza, czy socket jest połączony (`getpeername()` – inaczej `ConnectionError`).
5. Otwiera plik `rb` i w pętli czyta `chunk_size` bajtów:
   - jeśli `encryption` → chunk jest szyfrowany (`encryption.encrypt(chunk)`),
   - wysyła prefiks `struct.pack("!I", len(chunk_to_send))` (długość ZASZYFROWANEGO chunku),
   - wysyła `chunk_to_send`,
   - aktualizuje licznik `sent` (liczony na podstawie **niezaszyfrowanego** rozmiaru) i loguje postęp w %.
6. Błędy `FileNotFoundError`/`ConnectionError`/`OSError`/inne są logowane i **przekazywane dalej** (re-raise).

### 8.2 `recv_file(sock, dest_dir, filename, total_size, encryption=None) -> str`

1. `dest_path = os.path.join(dest_dir, filename)`, `os.makedirs(dest_dir, exist_ok=True)`.
2. Otwiera plik `wb` i w pętli, **dopóki `received < total_size`**:
   - czyta 4 bajty (`recv_all`) → `chunk_len` (`!I`),
   - czyta `chunk_len` bajtów → `chunk_data`,
   - jeśli `encryption` → próbuje odszyfrować; **przy błędzie deszyfrowania chunk traktuje jako niezaszyfrowany** (fallback),
   - zapisuje chunk, aktualizuje `received` (rozmiar po deszyfrowaniu), loguje postęp.
3. Obsługuje `OSError` → `ConnectionError`, `ClientDisconnected` → zamyka socket i **zwraca `None`** (przerwany transfer), inne wyjątki → re-raise.
4. Po zakończeniu zwraca `dest_path` (pełną ścieżkę zapisanego pliku).

### 8.3 Format transferu pliku po TCP

```
FILE_START (wiadomość Message)         <- metadane
[4B długości][chunk1 (szyfrowany)]     <- chunk 64 KB
[4B długości][chunk2 (szyfrowany)]
...
FILE_ACK (wiadomość Message)           <- potwierdzenie
```

---

## 9. Warstwa połączeniowa – `socket_utils.py`

- `BASE_DIR = os.path.expanduser("~/PhoneLink_received")` – bazowy katalog na odebrane pliki.
- Wyjątek `ClientDisconnected(Exception)`.
- `recv_all(sock, n)` – czyta dokładnie `n` bajtów w pętli:
  - pusty chunk (`b""`) → `ClientDisconnected` (drugi koniec zamknął połączenie),
  - `ConnectionResetError` → `ClientDisconnected` („reset polaczenia"),
  - `socket.timeout` → `TimeoutError` (z liczbą odebranych bajtów).
- Lokalizacje zapisu plików:
  - **klient → serwer:** `~/PhoneLink_received/from_clients/`,
  - **serwer → klient:** `~/PhoneLink_received/from_server/`.

---

## 10. Zeroconf / odkrywanie usług – `registerService.py`

- `get_local_ip()` – sprytna metoda: UDP socket, `connect(("8.8.8.8", 80))`, `getsockname()[0]`. To NIE wysyła ruchu – połączenie UDP ustawia trasę i odczytuje lokalne IP. Przy błędzie zwraca `"127.0.0.1"`.
- `connect()` rejestruje usługę w mDNS:
  - `service_type = "_phonelink._tcp.local."`
  - `service_name = "PhoneLink-Robert._phonelink._tcp.local."`
  - `port = 5000`
  - IP pakowane `socket.inet_aton(...)`
  - `properties`: `id="123456"`, `version="1"`, `cap="file,clipboard"` (deklaruje obsługę plików i schowka – schowek obecnie nie jest zaimplementowany).
- Na końcu `time.sleep(5)` – **blokuje wątek na 5 s** (m.in. by usługa zdążyła się rozgłosić).
- `if __name__ == "__main__":` – blok testowy do samodzielnego uruchomienia.

---

## 11. GUI – `UiLayer/gui.py`

Klasa `P2PGUI`:
- **Zależności:** `tkinter`, `ttk`, `filedialog`, `messagebox`, `tkinterdnd2` (DND_FILES, TkinterDnD).
- Konstruktor przyjmuje callback `on_file_selected_callback` – wołany przy wyborze pliku.
- Okno: tytuł **"P2P File Transfer"**, rozmiar **500x400**, tło **#2b2b2b** (ciemny motyw).
- Elementy:
  - `drop_frame` – ramka (tło #3b3b3b, relief RAISED), rozciągnięta.
  - `drop_label` – etykieta **"drop"** (biały tekst, font Arial 14, kursor `hand2`), zarejestrowana jako **cel drop** (`drop_target_register(DND_FILES)`, `dnd_bind('<<Drop>>')`).
  - kliknięcie w etykietę (`<Button-1>`) → otwiera okno wyboru pliku (`_browse_file`).
  - `status_label` – dolny pasek statusu, początkowo „Czekam na plik...".
- `_on_drop(event)` – czyści `{}`/cudzysłowy ze ścieżki (`strip('{}').strip('"').strip("'")`), aktualizuje status („Plik: <ścieżka>", zielony #4CAF50), woła callback.
- `_browse_file()` – `filedialog.askopenfilename()`, po wyborze to samo.
- `show_error(msg)` – ustawia status na czerwono i pokazuje `messagebox.showerror`.
- `run()` – `self.root.mainloop()`.

**Uwaga:** GUI pokazuje status wyboru pliku, ale sam transfer odbywa się w tle (wątek w `main.py`). GUI nie pokazuje postępu transferu (postęp drukowany jest w konsoli przez `send_file`/`recv_file`).

---

## 12. Znane ograniczenia, słabości i dziwactwa (analiza kodu)

1. **Klucz przesyłany jawnie** w handshake (`HANDSHAKE_ACK` zawiera klucz base64). Brak auth/DH → możliwy atak MITM i podsłuch. Poziom bezpieczeństwa to tylko „szyfrowanie w locie", nie „bezpieczne uzgadnianie".
2. **Jeden klient naraz** – `self.client` przechowuje tylko jedno połączenie; drugi klient nadpisze pierwszy bez zamykania poprzedniego gniazda.
3. **Downgrade do plaintext** – zarówno w `Message.deserialize`, jak i w `recv_file` błąd deszyfrowania nie jest traktowany jako błąd, tylko jako „dane niezaszyfrowane". To umożliwia wstrzyknięcie danych jawnych.
4. **`time.sleep(5)`** w `registerService.connect()` blokuje wątek główny przy starcie.
5. **`phone.py` usunięty** – w repo brak strony klienta; nie da się aktualnie uruchomić pełnego łańcucha bez przywrócenia klienta z gita.
6. **`send_file_to_client` ma parametr `mode="server"`, który nie jest używany** w ciele funkcji (martwy parametr).
7. **Brak limitów:** brak limitu rozmiaru pliku, brak transferu wznawialnego (resume), brak deduplikacji nazw – nadpisanie pliku o tej samej nazwie.
8. **Brak autoryzacji/tożsamości klienta** – każdy w sieci z kluczem może się połączyć (a klucz jest jawny).
9. **`handle_client` przerywa pętlę na pierwszym wyjątku**; po rozłączeniu klienta nie ma automatycznego wznowienia/ponownego podłączenia.
10. **`recv_file` zwraca `None` przy `ClientDisconnected`** – może prowadzić do `saved_path=None` w potwierdzeniu.
11. **Wyścig/zakleszczenie potencjalne:** w `main.py` transfery czekane są `join(timeout=10)` – jeśli trwa transfer dużego pliku, aplikacja może się „trząść" przy zamykaniu (daemon serwera zamyka się mimo to).
12. **`timeout 3600`** na sockecie klienta – po godzinie bezczynności socket się rozłączy (TimeoutError).
13. **Schemat `cap="file,clipboard"`** deklaruje obsługę schowka, ale **schowek nie jest zaimplementowany**.
14. **GUI nie pokazuje postępu** transferu (tylko konsola).
15. W `tcpServer.start()` po pętli `conn.close()` zamyka **ostatnie** zaakceptowane gniazdo, co przy wielokrotnych klientach jest niejednoznaczne.
16. `user_file_input` (interaktywna wysyłka pliku z klienta) została usunięta w ostatnim commicie.
17. Wiadomości/typy są **twardo kodowane** (brak rejestru typów), payload walidowany tylko ad hoc.

---

## 13. Historia zmian (git log – skrót)

```
86879c8 code reduction                     <- usunięcie phone.py, redukcja kodu (socket_utils, tcpServer, handshake, gui)
040280a test failed
b9c427b test failed
dd59caf working gui server -> client       <- działający serwer GUI → klient
ba3ac7f reduced logic in tcpServer
1f4b473 working P2P file transfer          <- działający transfer plików P2P
ee2ea9a / 0d56663 / e88501d more exceptions, small refactoring
940fe5a small changes, making it more scalable
24acddc working on server -> client file management
b12c553 / 6e8b48f / 48baedd tests
5b72c57 working message flow between client and server, including files
8e1d212 added test, CI/CD
a3b3896 Add comprehensive GitHub CI/CD workflow
93351ad working handshake                  <- działający handshake
c0e0bdd TCP server connection, laptop with mock-up phone  <- początek
```

Kierunek rozwoju widać w commitach: najpierw serwer TCP z „mock-up phone", potem handshake, protokół wiadomości, pliki, testy + CI/CD, potem GUI, a na końcu redukcja kodu i usunięcie klienta.

---

## 14. Testy – `tests/`

Konfiguracja (`pytest.ini`): `testpaths = tests`, wzorce `test_*.py`, opcje `--verbose --strict-markers --tb=short`, zdefiniowane markery: `slow`, `integration`, `unit`.

### 14.1 `test_encryption.py`
- `test_encrypt_decrypt` – szyfrowanie/deszyfrowanie (wynik różny od plaintext).
- `test_key_length` – `generate_key()` ma 32 B.
- `test_b64_encoding` – `get_key_b64()`/`from_b64()` zachowują klucz.
- `test_custom_key` – klucz podany do konstruktora jest zachowany.
- `test_encrypt_decrypt_multiple` – kilka wiadomości binarnych.
- `test_wrong_key_fails` – deszyfrowanie złym kluczem rzuca wyjątek.
- `test_derive_key_returns_correct_length` – PBKDF2 daje klucz 32 B i sól 16 B.

### 14.2 `test_file_transfer.py`
Oba testy uruchamiają **prawdziwy serwer TCP na 127.0.0.1 z portem losowym (0)** w osobnym wątku.
- `test_file_transfer_plain` – transfer bez szyfrowania; weryfikuje równość bajtów pliku.
- `test_file_transfer_encrypted` – transfer z `Encryption()`; weryfikuje równość bajtów.

### 14.3 `test_handshake.py`
- `test_handshake_flow` – pełny handshake client↔server na realnym sockecie; weryfikuje, że obie strony mają **ten sam klucz**.
- `test_message_encrypted_transmission` – serializacja zaszyfrowanej wiadomości, ręczne odszyfrowanie i sprawdzenie `type`/`payload`.

### 14.4 `test_socket_utils.py`
- `test_recv_all_small_data` – `recv_all` zbiera 11 B „Hello World".
- `test_recv_all_large_data` – `recv_all` zbiera >1 MB danych.
- `test_recv_all_timeout` – timeout rzuca `TimeoutError` po ustawionym czasie.

### 14.5 Uruchamianie
- `run_tests.sh`: `python -m pytest tests/ -v --tb=short --cov=Core --cov-report=html` → raport HTML w `htmlcov/index.html`.
- W CI (GitHub Actions): `pytest --maxfail=3 --disable-warnings -v --cov=Core --cov-report=xml --cov-report=term-missing`.

---

## 15. CI/CD – `.github/workflows/python-tests.yml`

- **Trigger:** push/PR na gałęzie `main` i `develop`.
- **Job `test`:** matrix Python **3.10, 3.11, 3.12, 3.13** na `ubuntu-latest`; cache pip; instalacja `pytest pytest-cov` + `requirements.txt`; uruchomienie testów z pokryciem; upload do **Codecov** (`coverage.xml`); na PR komentarz z pokryciem (`py-cov-action/python-coverage-comment-action`).
- **Job `lint`:** Python 3.13; instalacja `pylint flake8`; flake8 z opcjami:
  - `--select=E9,F63,F7,F82` (błędy krytyczne, pyflakes) z `--show-source --statistics`,
  - `--exit-zero --max-complexity=10 --max-line-length=127 --statistics`.

---

## 16. Pliki konfiguracyjne

### `requirements.txt` (pinned)
`cffi`, `coverage`, `cryptography==46.0.4`, `ifaddr`, `iniconfig`, `packaging`, `pluggy`, `pycparser`, `Pygments`, `pytest==9.0.2`, `pytest-cov`, `zeroconf==0.148.0`.

**Uwaga:** `tkinterdnd2` (używany przez GUI) **nie jest w requirements.txt** – trzeba go doinstalować osobno (`pip install tkinterdnd2`). W venv zainstalowany jest `tkinterdnd2-0.4.3`.

### `requirements-dev.txt`
`-r requirements.txt` + `pytest>=9.0`, `pytest-cov>=7.0`, `pytest-timeout>=2.1`, `flake8>=6.0`, `pylint>=3.0`, `black>=23.0`, `sphinx>=6.0`.

### `.flake8`
`max-line-length = 120`, wykluczenia: `venv,__pycache__,.git,.pytest_cache`; ignore `E203, W503`; per-file `__init__.py:F401`.

### `.gitignore`
`__pycache__`, pliki `*.pyc`, `venv/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `coverage.xml`, `.vscode/`, `.idea/`, `*.swp`, `*.swo`, pliki `.DS_Store`, `Thumbs.db`, `*.session`, `*.key`, `.env`, `dist/`, `build/`, `*.egg-info/`.

---

## 17. Zainstalowane zależności (venv – istotne)

- `cryptography 46.0.4`
- `zeroconf 0.148.0`
- `tkinterdnd2 0.4.3` (i `tkinterdnd2_pmgagne 0.3.0`)

---

## 18. Potencjalne kierunki rozwoju / co by model mógł dodać

- Przywrócenie klienta (nowy `phone.py` / aplikacja mobilna) korzystającego z `HandshakeManager.client_handshake` + `client_handle_message`.
- Bezpieczny handshake (Diffie-Hellman / ECDH + podpis, wymiana kluczy przez mDNS properties zamiast w plaintext).
- Obsługa wielu klientów (słownik/set zamiast pojedynczego `self.client`).
- Limity i wznawianie transferu, pasek postępu w GUI.
- Implementacja schowka (zgodnie z `cap="file,clipboard"`).
- Rejestr typów wiadomości + walidacja payloadów.
- Usunięcie fallbacku do plaintext przy błędzie deszyfrowania.
- `tkinterdnd2` dopisane do `requirements.txt`.
