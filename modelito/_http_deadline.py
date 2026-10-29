"""Private HTTP transport with a wall-clock deadline, including partial reads."""

from contextlib import contextmanager
import http.client
import math
import ipaddress
import queue
import socket
import threading
import time
from urllib.request import (
    HTTPHandler,
    HTTPSHandler,
    ProxyHandler,
    build_opener,
    getproxies,
)

# Match urllib's cached default opener: do not repeat OS proxy discovery per request.
_PROXIES = getproxies()


@contextmanager
def urlopen(url, timeout=60.0):
    """Open one request; shut down its sockets when the total budget expires."""
    timeout = float(timeout)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    deadline = time.monotonic() + timeout
    expired = threading.Event()
    lock = threading.Lock()
    sockets = []

    def expire():
        with lock:
            expired.set()
            for sock in sockets:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def remaining():
        budget = deadline - time.monotonic()
        if expired.is_set() or budget <= 0:
            raise TimeoutError("HTTP request deadline exceeded")
        return budget

    def create_connection(address, timeout=None, source_address=None, **kwargs):
        host, port = address
        # System DNS calls have no cancellation API. Bound the caller's wait;
        # the daemon resolver owns no request socket and cannot send a POST.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            resolved = queue.Queue(maxsize=1)

            def resolve():
                try:
                    resolved.put(socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM))
                except Exception as exc:
                    resolved.put(exc)

            threading.Thread(target=resolve, daemon=True).start()
            try:
                addresses = resolved.get(timeout=remaining())
            except queue.Empty as exc:
                raise TimeoutError("HTTP DNS deadline exceeded") from exc
            if isinstance(addresses, Exception):
                raise addresses
        else:
            addresses = socket.getaddrinfo(
                host, port, 0, socket.SOCK_STREAM, 0, socket.AI_NUMERICHOST
            )
        error = None
        for family, kind, proto, _, target in addresses:
            budget = remaining()
            sock = socket.socket(family, kind, proto)
            with lock:
                sockets.append(sock)
            try:
                sock.settimeout(budget)
                if source_address:
                    sock.bind(source_address)
                sock.connect(target)
                remaining()
                return sock
            except OSError as exc:
                sock.close()
                error = exc
        if error is not None:
            raise error
        raise OSError("No addresses for HTTP endpoint")

    class Connection(http.client.HTTPConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._create_connection = create_connection

    class TLSConnection(http.client.HTTPSConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._create_connection = create_connection

        def connect(self):
            http.client.HTTPConnection.connect(self)
            server_hostname = self._tunnel_host or self.host
            with lock:
                self.sock = self._context.wrap_socket(
                    self.sock,
                    server_hostname=server_hostname,
                    do_handshake_on_connect=False,
                )
                sockets.append(self.sock)
            self.sock.settimeout(remaining())
            self.sock.do_handshake()
            remaining()

    class HTTP(HTTPHandler):
        def http_open(self, request):
            return self.do_open(Connection, request)

    class HTTPS(HTTPSHandler):
        def https_open(self, request):
            return self.do_open(TLSConnection, request, context=self._context)

    timer = threading.Timer(timeout, expire)
    timer.daemon = True
    timer.start()
    try:
        with build_opener(ProxyHandler(_PROXIES), HTTP(), HTTPS()).open(
            url, timeout=timeout
        ) as response:
            yield response
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("HTTP request deadline exceeded")
    except Exception as exc:
        if expired.is_set() or time.monotonic() >= deadline:
            raise TimeoutError("HTTP request deadline exceeded") from exc
        raise
    finally:
        timer.cancel()
        timer.join()
