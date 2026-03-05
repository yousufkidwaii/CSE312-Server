from util.request import Request

def extract_credentials(request):
    body = request.body.decode("utf-8")
    parts = body.split("&")
    username = ""
    password = ""
    credentials = []

    for part in parts:
        if "=" not in part:
            return None
        key,value = part.split("=",1)
        if key == "username":
            username = value
            credentials.append(username)
        if key == "password":
            password = percent_decoding(value)
            credentials.append(password)

    return credentials

def percent_decoding(password):
    decoding = {
        "%21": "!",
        "%40": "@",
        "%23": "#",
        "%24": "$",
        "%25": "%",
        "%5E": "^",
        "%26": "&",
        "%28": "(",
        "%29": ")",
        "%2D": "-",
        "%5F": "_",
        "%3D": "="
    }
    decoded = ""
    i = 0
    while i <len(password):
        char = password[i]
        if char == "%":
            code = password[i:i+3]
            if code in decoding:
                decoded += decoding[code]
                i += 3
            else:
                raise ValueError("invalid percent encoding")
        else:
            decoded += password[i]
            i += 1

    return decoded

def validate_password(password):
    characters = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&()-_="
    special_chars = "!@#$%^&()-_="

    if len(password) < 8:
        return False
    lowercase = False
    uppercase = False
    numbers = False
    special = False

    for char in password:
        if char in characters:
            if char.islower():
                lowercase = True
            elif char.isupper():
                uppercase = True
            elif char.isdigit():
                numbers = True
            elif char in special_chars:
                special = True
        else:
            return False

    if lowercase and uppercase and numbers and special == True:
        return True



def extraction_test():
    req = Request(b'POST /api/users/settings HTTP/1.1\r\n'
                  b'Host: localhost:8080\r\n'
                  b'Accept: */*\r\n'
                  b'Content-Type: application/x-www-form-urlencoded\r\n'
                  b'Origin: http://localhost:8080\r\n'
                  b'Sec-Fetch-Site: same-origin\r\nSec-Fetch-Mode: cors\r\n'
                  b'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Safari/605.1.15\r\n'
                  b'Referer: http://localhost:8080/settings\r\n'
                  b'Sec-Fetch-Dest: empty\r\n'
                  b'Content-Length: 38\r\n'
                  b'Accept-Language: en-US,en;q=0.9\r\n'
                  b'Priority: u=3, i\r\n'
                  b'Accept-Encoding: gzip, deflate\r\n'
                  b'Cookie: session=fc16749e2efc495fb8aedb63f1a56adc\r\n'
                  b'Connection: keep-alive\r\n'
                  b'\r\n'
                  b'username=yousuf&password=8AM7w0fud9%21')
    actual = extract_credentials(req)
    expected = ["yousuf", "8AM7w0fud9!"]
    assert actual == expected
    print("yippee")

if __name__ == "__main__":
    extraction_test()





