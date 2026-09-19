# storage.py - Parmak izi isimlerini ve son giriş/çıkışları flash belleğe (JSON) kaydeder
import json


class Storage:
    """Sensör sadece numara (0,1,2...) saklar. Numaranın kime ait olduğunu (isim)
    ve son hareketleri burada tutuyoruz. Elektrik kesilse de kaybolmaz.

    names  : {"0": "Ali", "1": "Ayşe"}
    events : [["19.09.2026 14:03:11", "in", "Ali"], ...]   (eskiden yeniye)
             tür: "in" = giriş, "out" = çıkış, "deny" = reddedilen deneme
    """

    def __init__(self, max_events=20, names_file="names.json", events_file="events.json"):
        self.max_events = max_events
        self.names_file = names_file
        self.events_file = events_file
        self.names = self._load(names_file, {})
        self.events = self._load(events_file, [])

    # ---- dosya işlemleri ----
    def _load(self, path, default):
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return default                # dosya yok / bozuk -> boş başla

    def _save(self, path, data):
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except OSError:
            pass                          # flash dolu vs. -> sistem yine de çalışsın

    # ---- isimler ----
    def get_name(self, fid):
        return self.names.get(str(fid))

    def set_name(self, fid, name):
        self.names[str(fid)] = name
        self._save(self.names_file, self.names)

    def remove_name(self, fid):
        if str(fid) in self.names:
            del self.names[str(fid)]
            self._save(self.names_file, self.names)

    # ---- hareket kayıtları ----
    def add_event(self, when, kind, who):
        self.events.append([when, kind, who])
        while len(self.events) > self.max_events:
            self.events.pop(0)
        self._save(self.events_file, self.events)
