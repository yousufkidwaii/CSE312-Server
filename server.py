import socketserver
from util.request import Request
from util.router import Router
from util.hello_path import hello_path
from util.static_paths import serve_public, render_page
from util.chat_api import (create_chat, get_chats, update_chat, delete_chat,
                           add_reaction, remove_reaction,
                           update_nickname,
                           user_registration, user_login, user_logout, get_me, search_users, update_users,
                           upload_avatar, upload_video, get_videos, get_single_video)


class MyTCPHandler(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):
        self.router = Router()
        self.router.add_route("GET", "/hello", hello_path, True)
        #pages to render website
        self.router.add_route("GET", "/", render_page("index.html"), True)
        self.router.add_route("GET", "/chat", render_page("chat.html"), True)
        #static files
        self.router.add_route("GET", "/public", serve_public, False)
        #chat api
        self.router.add_route("POST", "/api/chats", create_chat, True)
        self.router.add_route("GET", "/api/chats", get_chats, True)
        self.router.add_route("PATCH", "/api/chats/", update_chat, False)
        self.router.add_route("DELETE", "/api/chats/", delete_chat, False)
        #emoji reactions
        self.router.add_route("PATCH","/api/reaction/", add_reaction, False)
        self.router.add_route("DELETE","/api/reaction/", remove_reaction, False)
        #nicknameeeeee
        self.router.add_route("PATCH","/api/nickname",update_nickname,False)
        #render hw2
        self.router.add_route("GET", "/register", render_page("register.html"), True)
        self.router.add_route("GET", "/login", render_page("login.html"), True)
        self.router.add_route("GET", "/settings", render_page("settings.html"), True)
        self.router.add_route("GET", "/search-users", render_page("search-users.html"), True)
        #registration
        self.router.add_route("POST","/register", user_registration, True)
        self.router.add_route("POST", "/login", user_login, True)
        self.router.add_route("GET","/logout",user_logout, True)
        self.router.add_route("GET", "/api/users/@me", get_me, True)
        self.router.add_route("GET", "/api/users/search", search_users, False)
        self.router.add_route("POST", "/api/users/settings", update_users, True)
        #render hw3
        self.router.add_route("GET", "/change-avatar", render_page("change-avatar.html"), True)
        self.router.add_route("GET", "/videotube", render_page("videotube.html"), True)
        self.router.add_route("GET", "/videotube/upload", render_page("upload.html"), True)
        self.router.add_route("GET", "/videotube/upload/{videoID}", render_page("view-video.html"), True)
        self.router.add_route("GET", "/videotube/set-thumbnail", render_page("set-thumbnail.html"), True)
        #avatar and video
        self.router.add_route("POST", "/api/users/avatar", upload_avatar, True)
        self.router.add_route("POST", "/api/videos", upload_video, True)
        self.router.add_route("GET", "/api/videos", get_videos, True)
        self.router.add_route("GET", "/api/videos/", get_single_video, False)
        super().__init__(request, client_address, server)

    def handle(self):
        received_data = self.request.recv(2048)
        if not received_data:
            return

        header_end = received_data.find(b"\r\n\r\n")
        if header_end == -1:
            return

        headers_part = received_data[:header_end]
        body_start = header_end + 4
        body = received_data[body_start:]

        content_length = 0
        for line in headers_part.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                value = line.split(b":", 1)[1].strip()
                content_length = int(value.decode())
                break

        while len(body) < content_length:
            chunk = self.request.recv(2048)
            if not chunk:
                break
            body += chunk

        full_request = headers_part + b"\r\n\r\n" + body

        print(self.client_address)
        print("--- received data ---")
        print(full_request)
        print("--- end of data ---\n\n")

        request = Request(full_request)

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