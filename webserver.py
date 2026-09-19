# webserver.py - ESP8266'nın kendi üzerinde çalışan mini web sunucusu (panel + JSON API)
import os
import gc
import json
import socket
import config
from utils import parse_query


def partition(text, sep):
    """MicroPython'da eksik olan str.partition işlevini simüle eder."""
    if sep in text:
        head, tail = text.split(sep, 1)
        return head, sep, tail
    return text, "", ""


class WebServer:
    """Engellemeyen (non-blocking) basit HTTP sunucusu. Ana döngüden poll() çağrılır;
    bekleyen bir tarayıcı isteği varsa cevaplar, yoksa hemen geri döner.

    Adresler:
      GET  /              -> index.html (panel)
      GET  /api/state     -> durum, parmak izleri, son hareketler, sistem mesajları (JSON)
      POST /api/enroll?name=Ali&key=ŞİFRE   -> yeni parmak izi kaydı başlat
      POST /api/delete?id=3&key=ŞİFRE       -> parmak izini sil

    `api` nesnesi (AccessController) şunları sağlamalı:
      get_state(), start_enroll(name), delete_finger(id)  -> (ok, mesaj)
    """

    def __init__(self, api, logger):
        self.api = api
        self.log = logger
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", config.WEB_PORT))
        self.sock.listen(3)
        self.sock.setblocking(False)                 # bekleyen istek yoksa accept() hata verir

    def poll(self):
        """Bekleyen bir istek varsa işler."""
        try:
            client, _ = self.sock.accept()
        except OSError:
            return                                   # bekleyen istek yok
        try:
            client.settimeout(2)
            self._handle(client)
        except Exception as e:
            self.log.log("WEB", "İstek hatası: {}".format(e))
        finally:
            client.close()
            gc.collect()

    # ---------------- istek yönlendirme ----------------
    def _handle(self, client):
        request = client.recv(1024)
        if not request:
            return
        parts = request.split(b"\r\n", 1)[0].decode().split(" ")
        if len(parts) < 2:
            return
        method, target = parts[0], parts[1]
        
        # DÜZELTİLEN SATIR: target.partition("?") yerine fonksiyon şeklinde çağırıyoruz
        path, _, query = partition(target, "?")
        params = parse_query(query)

        if path == "/":
            self._send_file(client, "index.html")
        elif path == "/api/state":
            self._send_json(client, self.api.get_state())
        elif path == "/api/enroll" and method == "POST":
            self._admin(client, params, lambda: self.api.start_enroll(params.get("name", "")))
        elif path == "/api/delete" and method == "POST":
            self._admin(client, params, lambda: self.api.delete_finger(params.get("id", "")))
        elif path == "/favicon.ico":
            self._send(client, "204 No Content", "text/plain", b"")
        else:
            self._send(client, "404 Not Found", "text/plain", b"404")

    def _admin(self, client, params, action):
        """Şifre doğruysa action()'ı çalıştırır. action (ok, mesaj) döndürür."""
        if params.get("key") != config.ADMIN_KEY:
            self.log.log("WEB", "Hatalı yönetici şifresi denendi")
            self._send_json(client, {"ok": False, "msg": "Şifre hatalı"}, "403 Forbidden")
            return
        ok, msg = action()
        self._send_json(client, {"ok": ok, "msg": msg})

    # ---------------- cevap gönderme ----------------
    def _header(self, status, ctype, length):
        return ("HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
                "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
                .format(status, ctype, length)).encode()

    def _send(self, client, status, ctype, body):
        client.write(self._header(status, ctype, len(body)))
        if body:
            client.write(body)

    def _send_json(self, client, obj, status="200 OK"):
        self._send(client, status, "application/json; charset=utf-8", json.dumps(obj).encode())

    def _send_file(self, client, path):
        """Dosyayı RAM'i şişirmeden 512 baytlık parçalarla gönderir."""
        try:
            size = os.stat(path)[6]
        except OSError:
            self._send(client, "404 Not Found", "text/plain", b"index.html yok")
            return
        client.write(self._header("200 OK", "text/html; charset=utf-8", size))
        with open(path, "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk:
                    break
                client.write(chunk)