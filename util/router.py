import util.response
class Router:

    def __init__(self):
        self.routes = []

    def add_route(self, method, path, action, exact_path=False):
        self.routes.append((method, path, action, exact_path))

    def route_request(self, request, handler):
        req_method = request.method
        req_path = request.path

        for method, path, action, exact_path in self.routes:
            if method != req_method:
                continue
            if exact_path:
                if req_path == path:
                    action(request, handler)
                    return
            else:
                if req_path.startswith(path):
                    action(request,handler)
                    return

        resp = util.response.Response().set_status(404, "Not Found").text("404 Not Found")
        handler.request.sendall(resp.to_data())
