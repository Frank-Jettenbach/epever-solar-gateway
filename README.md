# EPEVER Solar Controller - MQTT Gateway & Web Interface

Komplette Lösung zum Auslesen und Anzeigen von EPEVER Solarladeregler-Daten (XTRA-N / Tracer-AN Serie) via WiFi-Modul.

## Features

- **Web Interface**: Modernes Dashboard für alle Solardaten
- **MQTT Integration**: Automatische Übertragung an Home Assistant
- **Komplette Daten**: Echtzeitdaten, Statistiken und Einstellungen
- **Responsive Design**: Funktioniert auf Desktop und Mobile

## Hardware

- EPEVER XTRA-N 3210 Laderegler (oder kompatible Tracer-AN Serie)
- EPEVER WiFi-Modul (HF2421W oder ähnlich)
- Server/Raspberry Pi mit Python 3

## Installation

### 1. Repository klonen

```bash
cd /opt
git clone <repository-url> epever-mqtt-gateway
cd epever-mqtt-gateway
```

### 2. Virtual Environment erstellen

```bash
python3 -m venv venv
source venv/bin/activate
pip install pymodbus paho-mqtt flask
```

### 3. Konfiguration

```bash
cp .env.example .env
# .env editieren mit deinen Einstellungen
```

### 4. Apache Konfiguration (für Web Interface)

```bash
# Proxy-Module aktivieren
sudo a2enmod proxy proxy_http

# Konfiguration erstellen
sudo cat > /etc/apache2/conf-available/epever-proxy.conf << 'EOF'
<Location /epever>
    ProxyPass http://127.0.0.1:5050/
    ProxyPassReverse http://127.0.0.1:5050/
</Location>
EOF

# Aktivieren und neu laden
sudo a2enconf epever-proxy
sudo systemctl reload apache2
```

### 5. Systemd Service (optional)

```bash
sudo cp epever-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable epever-web
sudo systemctl start epever-web
```

### 6. MQTT Service für Home Assistant

```bash
# Einmalig testen
python mqtt_service.py --once

# Als Daemon (alle 60 Sekunden)
python mqtt_service.py --daemon

# Mit anderem Interval (z.B. 30 Sekunden)
python mqtt_service.py --daemon --interval 30

# Als Systemd Service installieren
sudo cp epever-mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable epever-mqtt
sudo systemctl start epever-mqtt
```

## Nutzung

### Web Interface

Nach der Installation erreichbar unter: `http://<server-ip>/epever/`

### Kommandozeile

```bash
# Alle Daten anzeigen
python epever_controller.py

# Interaktiver Modus
python epever_controller.py -i

# Daten an MQTT senden
python epever_controller.py --mqtt

# Nur Einstellungen anzeigen
python epever_controller.py --json | jq .settings
```

### MQTT zu Home Assistant

Das originale Skript sendet Daten an Home Assistant:

```bash
python epever-mqtt-gateway.py Sync2HA
```

## Modbus Register

### Echtzeitdaten (Input Registers 0x3100-0x311D)

| Register | Name | Einheit | Faktor |
|----------|------|---------|--------|
| 0x3100 | PV Spannung | V | 0.01 |
| 0x3101 | PV Strom | A | 0.01 |
| 0x3102-0x3103 | PV Leistung | W | 0.01 (32-bit) |
| 0x3104 | Batteriespannung | V | 0.01 |
| 0x3105 | Ladestrom | A | 0.01 |
| 0x3106-0x3107 | Ladeleistung | W | 0.01 (32-bit) |
| 0x310C | Lastspannung | V | 0.01 |
| 0x310D | Laststrom | A | 0.01 |
| 0x310E-0x310F | Lastleistung | W | 0.01 (32-bit) |
| 0x3110 | Batterietemperatur | °C | 0.01 |
| 0x3111 | Gerätetemperatur | °C | 0.01 |
| 0x311A | Batterie SOC | % | 1 |

### Statistiken (Input Registers 0x3300-0x3316)

| Register | Name | Einheit | Faktor |
|----------|------|---------|--------|
| 0x3300 | Max PV-Spannung heute | V | 0.01 |
| 0x3301 | Min Batteriespannung heute | V | 0.01 |
| 0x3302 | Max Batteriespannung heute | V | 0.01 |
| 0x3304-0x3305 | Verbrauch heute | kWh | 0.01 |
| 0x330A-0x330B | Verbrauch gesamt | kWh | 0.01 |
| 0x330C-0x330D | Erzeugung heute | kWh | 0.01 |
| 0x3312-0x3313 | Erzeugung gesamt | kWh | 0.01 |

### Einstellungen (Holding Registers 0x9000-0x904D)

| Register | Name | Einheit | Faktor |
|----------|------|---------|--------|
| 0x9000 | Batterietyp | - | 1 (0=Sealed, 1=GEL, 2=Flooded, 3=User, 4=LFP) |
| 0x9001 | Batteriekapazität | Ah | 1 |
| 0x9002 | Temperaturkompensation | mV/°C/2V | 1 |
| 0x9003 | High Voltage Disconnect | V | 0.01 |
| 0x9004 | Charging Limit Voltage | V | 0.01 |
| 0x9005 | Over Voltage Reconnect | V | 0.01 |
| 0x9006 | Equalize Voltage | V | 0.01 |
| 0x9007 | Boost Voltage | V | 0.01 |
| 0x9008 | Float Voltage | V | 0.01 |
| 0x9009 | Low Voltage Disconnect | V | 0.01 |
| 0x900A | Under Voltage Warning | V | 0.01 |
| 0x900B | Low Voltage Reconnect | V | 0.01 |
| 0x900C | Boost Reconnect Voltage | V | 0.01 |
| 0x900D | Low Voltage Disconnect 2 | V | 0.01 |
| 0x900E | Under Voltage Disconnect | V | 0.01 |
| 0x9013 | Boost Dauer | min | 1 |
| 0x9014 | Equalize Dauer | min | 1 |
| 0x903D | Last-Modus | - | 1 (0=Manual, 1=Light ON/OFF, ...) |
| 0x903E | Licht AN Verzögerung | min | 1 |
| 0x903F | Licht AUS Verzögerung | min | 1 |

## Bekannte Einschränkungen

### WiFi-Modul Schreibzugriff

Das EPEVER WiFi-Modul (HF2421W etc.) unterstützt **keine Modbus-Schreibbefehle** über die TCP-Schnittstelle. Das Web Interface ist daher auf "Nur Lesen" beschränkt.

**Lösungsmöglichkeiten:**
1. Einstellungen über Epever Solar Guardian App ändern
2. Einstellungen direkt am Display des Ladereglers ändern
3. RS485-USB-Adapter für direkten Schreibzugriff verwenden

### WiFi-Modul Verbindung

Das WiFi-Modul kann bei vielen gleichzeitigen Verbindungen instabil werden. Empfehlung:
- Maximal 1-2 Clients gleichzeitig
- Timeout-Werte in der Software berücksichtigen

## Dateien

```
/opt/epever-mqtt-gateway/
├── README.md                 # Diese Dokumentation
├── NOTES.md                  # Entwickler-Notizen
├── epever_controller.py      # Hauptmodul für Modbus-Kommunikation
├── epever-mqtt-gateway.py    # Original MQTT-Skript
├── mqtt_service.py           # MQTT Service (Daemon-fähig)
├── webapp.py                 # Flask Web Application
├── templates/
│   └── index.html            # Web Interface Template
├── epever-web.service        # Systemd Service (Web)
├── epever-mqtt.service       # Systemd Service (MQTT)
├── epever-apache.conf        # Apache VirtualHost Config
├── epever-apache-location.conf # Apache Location Config
├── .env.example              # Beispiel-Umgebungsvariablen
└── requirements.txt          # Python Dependencies
```

## API Endpunkte

Das Web Interface stellt folgende REST-APIs bereit:

| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/data` | Alle Daten (Echtzeit, Statistiken, Einstellungen) |
| `GET /api/realtime` | Nur Echtzeitdaten |
| `GET /api/statistics` | Nur Statistiken |
| `GET /api/settings` | Nur Einstellungen |
| `GET /api/battery-types` | Verfügbare Batterietypen |
| `GET /api/load-modes` | Verfügbare Last-Modi |

## Entwicklungshinweise

### Modbus-Datenformat

- Alle Spannungswerte werden mit Faktor 0.01 übertragen (z.B. 1354 = 13.54V)
- 32-Bit Werte (Leistung, Energie) werden als zwei 16-Bit Register übertragen (Little Endian)
- Temperaturen können negativ sein (signed)

### WiFi-Modul Besonderheiten

Das WiFi-Modul hat ein begrenztes Lese-Puffer:
- Register-Blöcke bis ca. 20 Register können auf einmal gelesen werden
- Bei größeren Blöcken werden leere Arrays zurückgegeben
- Schreibzugriffe werden nicht unterstützt (Timeout)

## Lizenz

MIT License - Freie Nutzung für private und kommerzielle Projekte.

## Mitwirkende

Entwickelt für die Integration eines EPEVER XTRA-N 3210 Ladereglers mit WiFi-Modul in Home Assistant.
