# main.py - Sistemin başlangıç noktası
import gc

gc.collect()

def start():
    from controller import AccessController
    gc.collect()
    app = AccessController()
    app.run()

if __name__ == "__main__":
    start()