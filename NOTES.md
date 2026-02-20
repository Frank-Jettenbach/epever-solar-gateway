# Entwicklungshinweise & Erinnerungen

## Projekt: EPEVER Solar Controller MQTT Gateway & Web Interface

### Hardware Setup
- **Laderegler**: EPEVER XTRA-N 3210 (MPPT, 30A, 12/24V)
- **WiFi-Modul**: EPEVER HF2421W (oder kompatibel)
- **IP**: 192.168.178.150
- **Port**: 8899 (Modbus TCP)
- **Login**: admin/admin

### Wichtige Erkenntnisse

#### 1. WiFi-Modul Beschränkungen

**Kein Schreibzugriff via Modbus TCP:**
- Das WiFi-Modul akzeptiert keine `write_register` Befehle
- Antwort: "No response received, expected at least 8 bytes (0 received)"
- Lösung: Einstellungen nur über App oder Display möglich

**Begrenzte Lese-Puffer:**
- Register-Blöcke bis ~20 Register funktionieren
- Bei größeren Blöcken: leere Arrays `[]`
- Einzelliest funktioniert immer

**HTTP API vorhanden aber undokumentiert:**
- Endpoint: `/cmd`
- Auth: Basic Auth (admin/admin)
- Format: `msg={"CID":<id>,"PL":<payload>}`
- CIDs: 10001=GET_STATE, 10003=GET_CONFIG, 10005=SET_CONFIG
- Timeouts bei Tests - weitere Untersuchung nötig

#### 2. Modbus Register Mapping

**Gültige Register für XTRA-N 3210:**

Erfolgreich getestet:
- 0x3100-0x3113 (Echtzeitdaten)
- 0x311A (SOC)
- 0x3300-0x3316 (Statistiken)
- 0x9000-0x901F (Einstellungen, mit Lücken)
- 0x903D-0x904D (Last-Einstellungen, mit Lücken)

Ungültige Register (FAIL):
- 0x311C, 0x3314, 0x900F, 0x9012, 0x9040, 0x9041, 0x904E, 0x904F

#### 3. Datenformat

**Spannungen:**
- Rohwert * 0.01 = Volt
- Beispiel: 1354 → 13.54V

**Leistungen (32-bit):**
- Low Word + (High Word << 16)
- Dann * 0.01

**Temperaturen:**
- signed int, * 0.01
- Können negativ sein

**SOC:**
- Direkt in Prozent (0-100)

#### 4. Batterietypen

```
0 = Sealed (Versiegelt)
1 = GEL
2 = Flooded (Offen)
3 = User (Benutzerdefiniert)
4 = LFP (LiFePO4)
5 = Li-NMC
```

### Apache Konfiguration

**Location-basiert (funktioniert):**
```apache
<Location /epever>
    ProxyPass http://127.0.0.1:5050/
    ProxyPassReverse http://127.0.0.1:5050/
</Location>
```

**VirtualHost (Alternative):**
```apache
<VirtualHost *:80>
    ServerName epever.local
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5050/
    ProxyPassReverse / http://127.0.0.1:5050/
</VirtualHost>
```

### Flask Webapp

**Start:**
```bash
source venv/bin/activate
python webapp.py
```

**API Endpunkte:**
- `/api/data` - Alle Daten
- `/api/realtime` - Echtzeitdaten
- `/api/statistics` - Statistiken
- `/api/settings` - Einstellungen

**Problem gelöst:**
- Import-Fehler: `sys.path.insert(0, os.path.dirname(...))`
- Dateiname: `epever_controller.py` (keine Bindestriche für Python-Imports)

### Systemd Service

```ini
[Unit]
Description=EPEVER Web Interface
After=network.target

[Service]
Type=simple
User=frank
WorkingDirectory=/opt/epever-mqtt-gateway
Environment="PATH=/opt/epever-mqtt-gateway/venv/bin"
ExecStart=/opt/epever-mqtt-gateway/venv/bin/python webapp.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Troubleshooting

**"Keine Verbindung zum EPEVER":**
1. IP prüfen: `ping 192.168.178.150`
2. Port prüfen: `nc -zv 192.168.178.150 8899`
3. WiFi-Modul neu starten
4. Zu viele Verbindungen? Warten und erneut versuchen

**Leere Daten / `[]`:**
- Register-Block zu groß
- Lösung: Kleinere Blöcke oder Einzelliest

**Flask startet nicht:**
- Port 5050 belegt? `ss -tlnp | grep 5050`
- Process killen: `pkill -f webapp.py`

### Home Assistant Integration

**MQTT Discovery:**
- Base Topic: `epever_xtra3210`
- Discovery Prefix: `homeassistant`
- Automatische Sensor-Erstellung

**Manual MQTT:**
```bash
python epever-mqtt-gateway.py Sync2HA
```

### Dateien im Projekt

| Datei | Zweck |
|-------|-------|
| `epever_controller.py` | Modbus-Kommunikation, Hauptklasse |
| `webapp.py` | Flask Web Application |
| `epever-mqtt-gateway.py` | Original MQTT-Skript |
| `templates/index.html` | Web Interface (HTML/CSS/JS) |
| `README.md` | Dokumentation |
| `NOTES.md` | Diese Entwickler-Notizen |

### Nächste Schritte / TODO

- [ ] WiFi-Modul HTTP API weiter untersuchen
- [ ] Schreibzugriff über HTTP API testen
- [ ] systemd Service für Autostart einrichten
- [ ] Logging implementieren
- [ ] Fehlerbehandlung verbessern
- [ ] Dashboard mit Charts erweitern
- [ ] Mobile App (optional)

### Referenzen

- EPEVER Website: https://www.epever.com
- EPEVER Support: https://www.epever.com/support/documents/
- Modbus Protokoll: Tracer-AN-Modbus-Protocol (PDF auf EPEVER Website)
- PyModbus Doku: https://pymodbus.readthedocs.io/

### GitHub Repository

- **URL**: https://github.com/Frank-Jettenbach/epever-solar-gateway
- **Name**: epever-solar-gateway

### WICHTIGE ERINNERUNGEN

#### WiFi-Modul Verbindung
- IP: 192.168.178.150
- Port: 8899
- Login: admin/admin
- Das Modul ist manchmal instabil - bei "No route to host" warten

#### MQTT Konfiguration
- Server: 192.168.178.57:1883
- User: tasmota
- Pass: Tasmota01$
- Device ID: epever_xtra3210

#### Services starten
```bash
# Web Interface
sudo systemctl start epever-web

# MQTT Service
sudo systemctl start epever-mqtt

# Oder manuell
/opt/epever-mqtt-gateway/venv/bin/python /opt/epever-mqtt-gateway/webapp.py &
/opt/epever-mqtt-gateway/venv/bin/python /opt/epever-mqtt-gateway/mqtt_service.py --daemon &
```

#### Nach Änderungen
1. Code ändern
2. Testen
3. `git add -A && git commit -m "Beschreibung"`
4. `git push`

#### Home Assistant
- Sensors erscheinen automatisch unter "EPEVER XTRA-N 3210"
- State Topic: `epever_xtra3210/state`
- Discovery Prefix: `homeassistant`

---

*Zuletzt aktualisiert: 20. Februar 2026*
