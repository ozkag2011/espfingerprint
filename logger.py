# logger.py - Sistem mesajlarını hem bilgisayara (USB terminal) hem web paneline gönderir
import utils


class Logger:
    """Mesajları iki yere yazar:
       1) print()  -> VS Code / MicroPico terminali (USB seri)
       2) hafıza   -> web panelindeki "Sistem mesajları" kutusu (son N satır)

    ÖNEMLİ: ESP8266'da sensör UART0'ı (USB ile aynı hat) kullanır. Sensör başladıktan
    sonra USB'ye yazmak sensörü bozacağı için `console` kapatılır; mesajlar web
    panelinden izlenir.
    """

    def __init__(self, max_lines=15):
        self.max_lines = max_lines
        self.lines = []
        self.console = True          # False olunca print() yapılmaz

    def log(self, tag, message):
        """Örn: log("ROLE", "Röle açıldı")  ->  [14:03:11] [ROLE] Röle açıldı"""
        line = "[{}] [{}] {}".format(utils.now_text()[11:], tag, message)
        if self.console:
            print(line)
        self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)
