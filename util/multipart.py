from util.request import Request

class Part:
    def __init__(self, headers, name, content):
        self.headers = headers
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
    return ''

def parse_headers(header_bytes):
    headers = {}
    lines = header_bytes.split(b'\r\n')
    for line in lines:
        if b":" in line:
            key, value = line.split(b":", 1)
            headers[key.decode().strip()] = value.decode().strip()
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
    boundary  = extract_boundary(content_type)
    boundary_bytes = b"--" + boundary.encode()
    raw_parts = request.body.split(boundary_bytes)
    parts = []

    for x in raw_parts:
        if x == b"" or x == b"--\r\n" or x == b"--":
            continue
        if x.startswith(b"\r\n"):
            x = x[2:]

        header_bytes, seperator, content = x.partition(b"\r\n\r\n")
        if seperator == b"":
            continue
        if content.endswith(b"\r\n"):
            content = content[:-2]
        headers = parse_headers(header_bytes)
        name = extract_name(headers)

        parts.append(Part(headers, name, content))
    return Multipart(boundary, parts)

def test1():
    raw_request = (
        b"POST /api/users/avatar HTTP/1.1\r\n"
        b"Host: localhost:8080\r\n"
        b"Accept: */*\r\n"
        b"Content-Type: multipart/form-data; boundary=----WebKitFormBoundarye9e8cJKbnTlnkloa\r\n"
        b"Origin: http://localhost:8080\r\n"
        b"Sec-Fetch-Site: same-origin\r\n"
        b"Sec-Fetch-Mode: cors\r\n"
        b"User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Safari/605.1.15\r\n"
        b"Referer: http://localhost:8080/change-avatar\r\n"
        b"Sec-Fetch-Dest: empty\r\n"
        b"Content-Length: 9999\r\n"
        b"Accept-Language: en-US,en;q=0.9\r\n"
        b"Priority: u=3, i\r\n"
        b"Accept-Encoding: gzip, deflate\r\n"
        b"Cookie: session=fc16749e2efc495fb8aedb63f1a56adc; auth_token=96cd4caf179746cfa0f6ea3c61d79cd3; Max-Age=0; HttpOnly=True\r\n"
        b"Connection: keep-alive\r\n"
        b"\r\n"
        b"------WebKitFormBoundarye9e8cJKbnTlnkloa\r\n"
        b"Content-Disposition: form-data; name=\"avatar\"; filename=\"IMG_2336.jpg\"\r\n"
        b"Content-Type: image/jpeg\r\n\r\n"
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x90\x00\x90\x00\x00"
        b"\xff\xe1\x01\x02Exif\x00\x00MM\x00*\x00\x00\x00\x08\x00\x07"
        b"\x01\x0e\x00\x02\x00\x00\x00\x0b\x00\x00\x00b\x01\x12\x00\x03"
        b"\x00\x00\x00\x01\x00\x01\x00\x00\x01\x1a\x00\x05\x00\x00\x00\x01"
        b"\x00\x00\x00n\x01\x1b\x00\x05\x00\x00\x00\x01\x00\x00\x00v"
        b"Screenshot\x00\x00\x00\x00"
        b"\r\n"
        b"------WebKitFormBoundarye9e8cJKbnTlnkloa--\r\n"
    )

    request = Request(raw_request)
    multipart = parse_multipart(request)

    assert multipart.boundary == "----WebKitFormBoundarye9e8cJKbnTlnkloa"
    assert len(multipart.parts) == 1

    part = multipart.parts[0]

    assert part.name == "avatar"
    assert part.headers["Content-Disposition"] == 'form-data; name="avatar"; filename="IMG_2336.jpg"'
    assert part.headers["Content-Type"] == "image/jpeg"

    assert part.content.startswith(b"\xff\xd8\xff\xe0")
    assert b"JFIF" in part.content
    assert b"Exif" in part.content
    assert b"Screenshot" in part.content

    print(multipart.boundary)
    print(part.name)
    print(part.headers)
    print(part.content[:40])


if __name__ == "__main__":
    test1()