import socket
import struct
import re
import time

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

    def execute(self, command, retry=True):
        """ Sends command and returns response text """
        if not self.sock:
             if not self.connect(): return ""
        try:
            # Packet type 2 is SERVERDATA_EXECCOMMAND
            # Use specific ID to track response? currently just using 2
            req_id = 100
            self.sock.send(self.pack(req_id, 2, command))
            
            # Read response
            # Header: size(4), request_id(4), type(4)
            header = self.sock.recv(12)
            if len(header) < 12: 
                raise ConnectionError("Incomplete header")
            
            size, res_id, typ = struct.unpack('<iii', header)
            
            # Body length = Size - 4 (ID) - 4 (Type)
            body_len = size - 8
            if body_len < 0: return ""
            
            data = b""
            while len(data) < body_len:
                chunk = self.sock.recv(min(4096, body_len - len(data)))
                if not chunk: break
                data += chunk
                
            # Remove null terminators
            return data.decode('utf-8', errors='ignore').strip('\x00')

        except Exception as e:
            self.sock = None
            if retry:
                # Try Once More
                print(f"[RCON] Connection lost ({e}), reconnecting...")
                return self.execute(command, retry=False)
            return ""

    def get_players(self):
        """ Returns list of dict {name, unknown} """
        raw = self.execute("players")
        # Format:
        # Players connected (1):
        # - Konijima
        
        # Debugging: Dump raw response to a file just in case
        # try:
        #     with open("last_rcon_players.log", "w") as f:
        #         f.write(raw)
        # except: pass
            
        lines = raw.split('\n')
        players = []
        for line in lines:
            line = line.strip()
            if not line: continue
            if "Players connected" in line: continue
            
            # Remove generic list bullet points if present, but also accept plain names
            # Standard: "- Name"
            if line.startswith("-") or line.startswith("*"):
                name = line[1:].strip()
            else:
                name = line
            
            if name:
                players.append({"name": name})
        return players

    def is_admin_online(self):
        """ Checks if the 'admin' account is online """
        players = self.get_players()
        for p in players:
            if p['name'].lower() == 'admin':
                return True
        return False

    def kick(self, user, reason="Kicked by Admin"):
        self.execute(f'kickuser "{user}" -r "{reason}"')
        
    def ban(self, user, ip=False, reason="Banned by Admin"):
        cmd = 'banuser' if not ip else 'banid' 
        # CAREFUL: banid usually takes SteamID, banuser takes name. Assume name for simplicity here.
        self.execute(f'banuser "{user}" -r "{reason}"')

    def broadcast(self, message):
        # PZ specific command usually: servermsg "message"
        self.execute(f'servermsg "{message}"')


    def quit(self):
        self.send("quit")
        self.send("save") # Just in case
