class Request:

    def __init__(self, request: bytes):
        self.body = b""
        self.method = ""
        self.path = ""
        self.http_version = ""
        self.headers = {}
        self.cookies = {}

        # Try to split headers/body; if separator missing, treat everything as headers (best-effort)
        header_bytes, sep, body = request.partition(b"\r\n\r\n")
        if sep:
            self.body = body
        else:
            header_bytes = request
            self.body = b""

        # Decode headers safely
        header_text = header_bytes.decode("utf-8", errors="replace")
        lines = header_text.split("\r\n")

        # Need at least the request line
        if len(lines) == 0 or lines[0].strip() == "":
            raise ValueError("Invalid request line")

        request_line = lines[0]
        parts = request_line.split(" ")
        if len(parts) != 3:
            raise ValueError("Invalid request line")

        self.method = parts[0]
        self.path = parts[1]
        self.http_version = parts[2]

        # Headers
        for line in lines[1:]:
            if not line:
                continue
            if ":" not in line:
                # Ignore malformed/incomplete header lines instead of crashing
                continue
            key, value = line.split(":", 1)
            self.headers[key] = value.strip()

        # Cookies
        if "Cookie" in self.headers:
            cookie_header = self.headers["Cookie"]
            for pair in cookie_header.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    self.cookies[k] = v



def test1():
    request = Request(b'GET / HTTP/1.1\r\nHost: localhost:8080\r\nConnection: keep-alive\r\n\r\n')
    assert request.method == "GET"
    assert "Host" in request.headers
    assert request.headers["Host"] == "localhost:8080"  # note: The leading space in the header value must be removed
    assert request.body == b""  # There is no body for this request.
    # When parsing POST requests, the body must be in bytes, not str

    # This is the start of a simple way (ie. no external libraries) to test your code.
    # It's recommended that you complete this test and add others, including at least one
    # test using a POST request. Also, ensure that the types of all values are correct


if __name__ == '__main__':
    test1()
