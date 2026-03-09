from util.request import Request

class Multipart:
    def __init__(self, request, parts):
        self.boundary = ""
        self.parts = []
        self.boundary = str(request.headers["Content-Type"])
        self.parts = [parts._headers, parts.name, parts.content]

class Parts:
    def __init__(self, request):
        self._headers = {}
        self.name = ""
        self.content = b''

        self._headers = request.headers
        self.name = str(request.headers["Content-Disposition"])
        self.content = request.body

def parse_multipart(request):
    parts = Parts(request)
    multipart = Multipart(request, parts)
    return multipart