from Core.ConnectionLayer.registerService import RegisterService
from Core.ConnectionLayer.tcpServer import tcpServer
import threading

service = RegisterService()
HOST = service.get_local_ip()
PORT = 5000  

server = tcpServer(HOST, PORT)

server_thread = threading.Thread(target=server.start, daemon=True)
server_thread.start()
service.connect()

print("Serwer gotów. Komendy:")
print("  send <plik> - wysłij plik do klienta")
print("  exit - zatrzymaj serwer")

while True:
    cmd = input(">>> ").strip()

    if cmd == "exit":
        server.stop()
        break

    elif cmd.startswith("send "):
        filename = cmd.replace("send ", "").strip()
        server.send_file_to_client(filename)

    else:
        print("Nieznana komenda. Dostępne: send <plik>, exit")    