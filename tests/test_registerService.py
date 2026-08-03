import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.ConnectionLayer.registerService import RegisterService


def test_connect_returns_immediately():
    service = RegisterService()
    start = time.time()
    service.connect()
    elapsed = time.time() - start

    assert elapsed < 0.5, f"connect() nie może blokować wątku głównego (zajęło {elapsed:.2f}s)"
    service.close()


def test_close_is_idempotent():
    service = RegisterService()
    service.connect()
    service.close()
    service.close()
