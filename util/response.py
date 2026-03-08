import json


class Response:
    def __init__(self):
        self.status_code = 200
        self.status_text = "OK"

        self.header_store = {}
        self.cookie_store = {}
        self.body_store = b""


    def set_status(self, code, text):
        self.status_code = int(code)
        self.status_text = str(text)
        return self

    def headers(self, headers):
        for k in headers:
            self.header_store[str(k)] = str(headers[k])
        return self

    def cookies(self, cookie_dict):
        if not cookie_dict:
            return self

        items = list(cookie_dict.items())
        main_cookie_name, main_cookie_value = items[0]
        directives = items[1:]

        cookie_entry = {
            "value": main_cookie_value,
            "directives": directives
        }

        if main_cookie_name not in self.cookie_store:
            self.cookie_store[main_cookie_name] = []
        self.cookie_store[main_cookie_name].append(cookie_entry)

        return self

    def bytes(self, data):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes or bytearray")
        self.body_store += bytes(data)
        return self

    def text(self, data):
        if not isinstance(data,str):
            raise TypeError("data must be str")
        self.body_store += data.encode("utf-8")
        return self

    def json(self, data):
        if not isinstance(data, (dict, list)):
            raise TypeError("data must be dict or list")
        json_bytes = json.dumps(data).encode("utf-8")
        self.body_store = json_bytes
        self.header_store["Content-Type"] = "application/json"
        return self

    def to_data(self):
        self.header_store["X-Content-Type-Options"] = "nosniff"

        if "Content-Type" not in self.header_store:
            self.header_store["Content-Type"] = "text/plain; charset=utf-8"
        self.header_store["Content-Length"] = str(len(self.body_store))

        response_lines = [f"HTTP/1.1 {self.status_code} {self.status_text}"]

        for k, v in self.header_store.items():
            response_lines.append(f"{k}: {v}")

        for cookie_name, cookie_entries in self.cookie_store.items():
            for entry in cookie_entries:
                cookie_line = f"Set-Cookie: {cookie_name}={entry['value']}"
                for k, v in entry['directives']:
                    if v is True or v is None:
                        cookie_line += f"; {k}"
                    else:
                        cookie_line += f"; {k}={v}"
                response_lines.append(cookie_line)

        response_lines.append("")
        return "\r\n".join(response_lines).encode("utf-8") + b"\r\n" + self.body_store


def test1():
    #res = Response(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: 5\r\n\r\nhello')
    res = Response()
    res.cookies(
        {"auth_token": "123",
         "Max-Age": "0",
         "HttpOnly": None,}
    )
    expected = b'HTTP/1.1 200 OK\r\nX-Content-Type-Options: nosniff\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: 0\r\nSet-Cookie: auth_token=123; Max-Age=0; HttpOnly\r\n\r\n'
    actual = res.to_data()
    print(actual.decode())
    print(expected.decode())

    assert actual == expected
if __name__ == '__main__':
    test1()
