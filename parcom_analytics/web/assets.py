"""Loopback GET-only static assets, with no HTTP bridge endpoints."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit


class AssetHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def list_directory(self, path):
        self.send_error(404)


def serve(root):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(AssetHandler, directory=str(root)))
    Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/index.html"


def allowed_navigation(target, entry):
    destination, source = urlsplit(target), urlsplit(entry)
    return (destination.scheme, destination.netloc, destination.path, destination.query) == (source.scheme, source.netloc, source.path, source.query)
