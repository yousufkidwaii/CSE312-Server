from util.request import Request

class Part:
    def __init__(self, headers, name, content):
        self.boundary = headers
        self.name = name
        self.content = content

class Multipart:
    def __init__(self, boundary, parts):
        self.boundary = boundary
        self.parts = parts

def extract_boundary(content_type):
    parts = content_type.split(";")
    for part in parts:
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary="):]
            return boundary.strip('"')
    return ""

def parse_headers(header_bytes):
    headers = {}
    lines = header_bytes.decode().split("\r\n")
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key] = value
    return headers

def extract_name(headers):
    cd = headers.get("Content-Disposition", "")
    parts = cd.split(";")
    for part in parts:
        part = part.strip()
        if part.startswith("name="):
            name = part[len("name="):]
            return name.strip('"')
    return ""

def parse_multipart(request):
    content_type = request.headers.get("Content-Type", "")
    boundary = extract_boundary(content_type) #4
    body = request.body
    boundary_bytes = b"--" + boundary.encode()
    parts = []
    count = 0
    while True:
        start = body.find(boundary_bytes, count)
        if start == -1:
            break
        start += len(boundary_bytes)
        #closing boundary
        if body[start:start + 2] == b"--":
            break
        #skip crlf
        header_end = body.find(b'\r\n\r\n', start)
        if header_end == -1:
            break
        header_bytes = body[start:header_end]
        headers = parse_headers(header_bytes) #1
        name = extract_name(headers) #2

        content_start = header_end + 4

        next_boundary = body.find(b"\r\n" + boundary_bytes, content_start)
        if next_boundary == -1:
            break
        content = body[content_start:next_boundary] #3
        parts.append(Multipart(headers, name, content)) #5
        count = next_boundary + 2
    return Multipart(boundary, parts)