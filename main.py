from Core.ConnectionLayer.registerService import RegisterService
from Core.ConnectionLayer.tcpServer import tcpServer
import threading
from UiLayer.gui import P2PGUI

service = RegisterService()
HOST = service.get_local_ip()
PORT = 5000  

server = tcpServer(HOST, PORT)

server_thread = threading.Thread(target=server.start, daemon=True)
server_thread.start()
service.connect()


active_transfers = []

def on_file_selected(filepath):
    transfer_thread = threading.Thread(
        target=server.send_file_to_client,
        args=(filepath,),
        daemon=False  
    )
    active_transfers.append(transfer_thread)
    transfer_thread.start()
gui = P2PGUI(on_file_selected_callback=on_file_selected)
gui.run()
for t in active_transfers:
    if t.is_alive():
        t.join(timeout=10)  
server.stop()