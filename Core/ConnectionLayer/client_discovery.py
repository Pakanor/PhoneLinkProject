import socket
import threading
from zeroconf import Zeroconf, ServiceBrowser


class ServerDiscovery:
    SERVICE_TYPE = "_phonelink._tcp.local."

    def __init__(self, timeout: float = 5.0, service_name: str = None):
        self.timeout = timeout
        self.service_name = service_name
        self._zeroconf = None
        self._browser = None
        self._found_event = threading.Event()
        self._service_info = None

    def add_service(self, zeroconf, service_type, name):
        if self.service_name is not None and name != self.service_name:
            return
        info = zeroconf.get_service_info(service_type, name)
        if info and info.port:
            self._service_info = info
            self._found_event.set()

    def remove_service(self, zeroconf, service_type, name):
        pass

    def update_service(self, zeroconf, service_type, name):
        self.add_service(zeroconf, service_type, name)

    def find_server(self):
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(self._zeroconf, self.SERVICE_TYPE, self)
        self._found_event.wait(timeout=self.timeout)
        self.close()
        if self._service_info is None:
            raise TimeoutError("Nie znaleziono serwera PhoneLink w sieci")
        ip = socket.inet_ntoa(self._service_info.addresses[0])
        port = self._service_info.port
        return ip, port

    def close(self):
        if self._browser is not None:
            try:
                self._browser.cancel()
            except Exception:
                pass
            self._browser = None
        if self._zeroconf is not None:
            try:
                self._zeroconf.close()
            except Exception:
                pass
            self._zeroconf = None
