# =====================================================================
#  config.py  -  Projenin TÜM ayarları burada (pinler, Wi-Fi, süreler)
# =====================================================================
#
#  NodeMCU pin etiketi -> GPIO numarası (kodda GPIO numarası kullanılır)
#     D0=16  D1=5  D2=4  D3=0  D4=2  D5=14  D6=12  D7=13  D8=15
#     TX=1   RX=3
#
#  BAĞLANTI ŞEMASI
#  ---------------
#  Ekran (GMT130-V1.0 / ST7789 / 240x240)      ESP8266 (NodeMCU)
#     BLK  ------------------------------------  D1
#     DC   ------------------------------------  D2
#     RES  ------------------------------------  D4
#     SDA  ------------------------------------  D8   (hızlı SPI için D7)
#     SCL  ------------------------------------  D7   (hızlı SPI için D5)
#     VCC  ------------------------------------  3V3
#     GND  ------------------------------------  GND
#
#  Adafruit parmak izi sensörü (TX/RX çapraz bağlanır!)
#     Sensör TX  -----------------------------  RX  (GPIO3)
#     Sensör RX  -----------------------------  TX  (GPIO1)
#     VIN        -----------------------------  3V3
#     GND        -----------------------------  GND
#
#  Röle modülü:  IN (sinyal) -----------------  D0
#  İç kapı butonu:  bir ucu D3, diğer ucu GND
# =====================================================================

# ---------------------------- Wi-Fi ----------------------------------
WIFI_SSID = "WİFİ-AD"
WIFI_PASSWORD = "WİFİ-ŞİFRE"
TIMEZONE_HOURS = 3            # Saat dilimi (UTC+3 = Türkiye)

# ------------------------- Web paneli --------------------------------
WEB_PORT = 80
ADMIN_KEY = "1234"            # Parmak izi ekleme/silme şifresi -> MUTLAKA DEĞİŞTİRİN

# ------------------------------ Pinler -------------------------------
PIN_TFT_BLK = 5               # D1  arka ışık
PIN_TFT_DC = 4                # D2  komut/veri seçici
PIN_TFT_RES = 2               # D4  reset
PIN_TFT_SCK = 13              # D7  SCL (sadece yazılımsal SPI'da kullanılır)
PIN_TFT_SDA = 15              # D8  SDA (sadece yazılımsal SPI'da kullanılır)
PIN_TFT_MISO = 14             # D5  ekranda YOK; SoftSPI sadece formalite için ister

PIN_RELAY = 16                # D0  röle sinyal
PIN_BUTTON = 0                # D3  iç buton (diğer ucu GND)

# ------------------------------ Ekran --------------------------------
# False: kağıttaki bağlantıyla çalışır (D7=SCL, D8=SDA) ama ekran yavaş boyanır.
# True : ESP8266'nın donanım SPI'ı. SCL -> D5, SDA -> D7 olarak taşıyın (~50 kat hızlı).
TFT_HW_SPI = False
TFT_SPI_POLARITY = 1          # Ekran çöp gösterirse (1,0) yerine (1,1) veya (0,0) deneyin
TFT_SPI_PHASE = 0
TFT_BGR = False               # Kırmızı ile mavi yer değiştirmişse True yapın

# ------------------------------ Röle ---------------------------------
RELAY_ACTIVE_LOW = True       # Çoğu röle modülü LOW ile çeker. Tersiyse False yapın.
RELAY_OPEN_MS = 3000          # Kapı kilidi kaç ms açık kalsın

# ------------------------ Parmak izi sensörü -------------------------
SENSOR_ENABLED = True         # False: sensörsüz test. USB terminali (print) çalışmaya devam eder.
FP_BAUD = 57600               # Adafruit sensör varsayılanı
FP_MAX_FAILS = 5              # Üst üste bu kadar kayıtsız parmakta...
FP_LOCKOUT_S = 30             # ...bu kadar saniye sensör okumayı durdur

# ------------------------------ Diğer --------------------------------
SERVICE_WINDOW_S = 6          # Açılışta Ctrl+C ile durdurup kod yükleyebileceğiniz süre
RESULT_SCREEN_MS = 2500       # Yeşil/kırmızı sonuç ekranı ne kadar kalsın
MAX_EVENTS = 20               # Web panelinde tutulacak son giriş/çıkış sayısı
LOG_LINES = 15                # Web panelindeki sistem mesajı satır sayısı
