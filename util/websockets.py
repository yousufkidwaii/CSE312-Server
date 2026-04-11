import hashlib
import base64

class WebSocketFrame:
    def __init__(self, fin_bit, opcode, payload_length, payload):
        self.fin_bit = fin_bit
        self.opcode = opcode
        self.payload_length = payload_length
        self.payload = payload

def compute_accept(ws_key):
    magic_string = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    combined = ws_key + magic_string
    hashed = hashlib.sha1(combined.encode()).digest()
    accept = base64.b64encode(hashed).decode()
    return accept

def parse_ws_frame(frame_bytes):
    first_byte = frame_bytes[0]
    second_byte = frame_bytes[1]
    fin_bit = (first_byte >> 7) & 1
    opcode = first_byte & 0b00001111
    mask_bit = (second_byte >> 7) & 1
    len_indicator = second_byte & 0b01111111

    i = 2
    if len_indicator <= 125:
        payload_len = len_indicator
    elif len_indicator == 126:
        payload_len = int.from_bytes(frame_bytes[i:i+2], "big")
        i += 2
    else:
        payload_len = int.from_bytes(frame_bytes[i:i+8], "big")
        i += 8

    mask_key = b""
    if mask_bit == 1:
        mask_key = frame_bytes[i:i+4]
        i += 4
    mask_payload = frame_bytes[i:i+payload_len]

    if mask_bit == 1:
        unmask_payload = b""
        for i in range(payload_len):
            unmask_payload += bytes([mask_payload[i] ^ mask_key[i % 4]])
    else:
        unmask_payload = mask_payload

    return WebSocketFrame(fin_bit, opcode, payload_len, unmask_payload)

def generate_ws_frame(payload_bytes):
    first_byte = 0b10000001
    payload_len = len(payload_bytes)
    if payload_len <= 125:
        header = bytes([first_byte, payload_len])
    elif payload_len <= 65535:
        header = bytes([first_byte, 126]) + payload_len.to_bytes(2, "big")
    else:
        header = bytes([first_byte, 127]) + payload_len.to_bytes(8, "big")

    return header + payload_bytes

