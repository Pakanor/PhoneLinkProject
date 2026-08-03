from Core.ConnectionLayer.registerService import RegisterService
from Core.ConnectionLayer.tcpServer import tcpServer
import queue
import threading
from UiLayer.gui import P2PGUI


def main():
    service = RegisterService()
    host = service.get_local_ip()
    port = 5000

    event_queue = queue.Queue()
    server = tcpServer(host, port, event_queue=event_queue)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    service.connect()

    active_transfers = []

    def on_file_selected(filepath, client_id=None):
        transfer_thread = threading.Thread(
            target=server.send_file_to_client,
            args=(filepath,),
            kwargs={"client_id": client_id},
            daemon=False
        )
        active_transfers.append(transfer_thread)
        transfer_thread.start()

    try:
        gui = P2PGUI(event_queue, on_file_selected_callback=on_file_selected, server=server)
        gui.run()
    finally:
        for t in active_transfers:
            if t.is_alive():
                t.join(timeout=10)
        server.stop()
        service.close()


if __name__ == "__main__":
    main()
