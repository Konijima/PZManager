import socket
import struct

class RCONClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = int(port)
        self.password = password
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))
            if not self.auth():
                print(f"[RCON] Auth Failed for {self.host}:{self.port}")
                self.sock.close()
                self.sock = None
                return False
            return True
        except Exception as e:
            print(f"[RCON] Connection Failed: {e}")
            self.sock = None
            return False

    def pack(self, path_id, type_id, body):
        size = len(body) + 10
        return struct.pack('<iii', size, path_id, type_id) + body.encode('utf-8') + b'\x00\x00'

    def auth(self):
        self.sock.send(self.pack(1, 3, self.password))
        try:
            response = self.sock.recv(4096)
            if len(response) >= 12:
                # 12 byte header: size(4), request_id(4), type(4)
                size, req_id, typ = struct.unpack('<iii', response[:12])
                return req_id != -1
            return False
        except: return False

    def send(self, command):
        if not self.sock: 
            if not self.connect(): return
        try:
            self.sock.send(self.pack(2, 2, command))
            return True
        except:
            self.sock = None
            return False
            
    def broadcast(self, message):
        # PZ specific command usually: servermsg "message"
        self.send(f'servermsg "{message}"')

    def quit(self):
        self.send("quit")
        self.send("save") # Just in case
