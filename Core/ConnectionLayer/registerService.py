from zeroconf import Zeroconf, ServiceInfo
import socket
import threading


class RegisterService:
    def __init__(self):
        self._zeroconf = None
        self._info = None
        self._stop_event = threading.Event()
        self._thread = None

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except OSError:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def connect(self):
        service_type = "_phonelink._tcp.local."
        service_name = "PhoneLink-Robert._phonelink._tcp.local."
        port = 5000
        ip = socket.inet_aton(self.get_local_ip())

        properties = {
            b"id": b"123456",
            b"version": b"1",
            b"cap": b"file,clipboard"
        }

        self._info = ServiceInfo(
            service_type,
            service_name,
            addresses=[ip],
            port=port,
            properties=properties
        )

        self._thread = threading.Thread(target=self._register_loop, daemon=True)
        self._thread.start()

    def _register_loop(self):
        try:
            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(self._info)
            print("[RegisterService] Usługa zarejestrowana w mDNS")
            self._stop_event.wait()
        except Exception as e:
            print(f"[RegisterService] Błąd rejestracji usługi: {e}")
        finally:
            if self._zeroconf is not None:
                try:
                    self._zeroconf.unregister_service(self._info)
                except Exception as e:
                    print(f"[RegisterService] Błąd wyrejestrowania: {e}")
                try:
                    self._zeroconf.close()
                except Exception as e:
                    print(f"[RegisterService] Błąd zamykania zeroconf: {e}")
                self._zeroconf = None

    def close(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


if __name__ == "__main__":
    service = RegisterService()
    service.connect()
