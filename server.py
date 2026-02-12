import socketserver
from util.request import Request
from util.router import Router
from util.hello_path import hello_path
from util.static_paths import serve_public, render_page


class MyTCPHandler(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):
        self.router = Router()
        self.router.add_route("GET", "/hello", hello_path, True)
        #pages to render website
        self.router.add_route("GET", "/", render_page("index.html"), True)
        self.router.add_route("GET", "/chat", render_page("chat.html"), True)
        #static files
        self.router.add_route("GET", "/public", serve_public, False)
        super().__init__(request, client_address, server)

    def handle(self):
        received_data = self.request.recv(2048)
        print(self.client_address)
        print("--- received data ---")
        print(received_data)
        print("--- end of data ---\n\n")
        request = Request(received_data)

        self.router.route_request(request, self)


def main():
    host = "0.0.0.0"
    port = 8080
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    server = socketserver.ThreadingTCPServer((host, port), MyTCPHandler)

    print("Listening on port " + str(port))
    server.serve_forever()


if __name__ == "__main__":
    main()