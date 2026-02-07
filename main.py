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
while True:
    cmd = input(">>> ").strip()

    if cmd == "exit":
        server.stop()
        break

    elif cmd == "send":
        filename = input("Podaj nazwę pliku: ").strip()

    elif cmd == "help":
        print("send - wyslij plik")
        print("exit - zatrzymaj serwer")    