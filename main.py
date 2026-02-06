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
if input("Press Enter to stop the server...\n") == "exit":
    server.stop()