Dont run anymore

import sys
import time
import json
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt



# --- KONFIGURATION ---
EPEVER_HOST = '192.168.178.150'
EPEVER_PORT = 8899
SLAVE_ID = 1

MQTT_SERVER = "192.168.178.57"  # <--- BITTE ANPASSEN
MQTT_PORT = 1883
MQTT_USER = "tasmota"
MQTT_PASS = "Tasmota01$"

DEVICE_ID = "epever_xtra3210"
DISCOVERY_PREFIX = "homeassistant"

def decode_32bit(low, high):
    return (high << 16) | low

# --- REGISTER DEFINITIONEN (Alle Register + Gliederung + HA-Klassen) ---
SENSORS = [
    # --- Kategorie: Echtzeit ---
    (0x3100, "pv_voltage", "PV-Spannung", "V", 0.01, "input", "Echtzeit", "voltage", "measurement"),
    (0x3101, "pv_current", "PV-Strom", "A", 0.01, "input", "Echtzeit", "current", "measurement"),
    (0x3102, "pv_power", "PV-Leistung", "W", 0.01, "input_32", "Echtzeit", "power", "measurement"),
    (0x3104, "bat_voltage", "Batterie-Spannung", "V", 0.01, "input", "Echtzeit", "voltage", "measurement"),
    (0x3105, "charge_current", "Lade-Strom", "A", 0.01, "input", "Echtzeit", "current", "measurement"),
    (0x3106, "charge_power", "Lade-Leistung", "W", 0.01, "input_32", "Echtzeit", "power", "measurement"),
    (0x310C, "load_voltage", "Last-Spannung", "V", 0.01, "input", "Echtzeit", "voltage", "measurement"),
    (0x310D, "load_current", "Last-Strom", "A", 0.01, "input", "Echtzeit", "current", "measurement"),
    (0x310E, "load_power", "Last-Leistung", "W", 0.01, "input_32", "Echtzeit", "power", "measurement"),
    (0x3110, "bat_temp", "Batterie-Temperatur", "°C", 0.01, "input", "Echtzeit", "temperature", "measurement"),
    (0x3111, "dev_temp", "Geräte-Temperatur", "°C", 0.01, "input", "Echtzeit", "temperature", "measurement"),
    (0x311A, "bat_soc", "Batterie-SOC", "%", 1, "input", "Echtzeit", "battery", "measurement"),
    
    # --- Kategorie: Statistik Heute ---
    (0x330C, "energy_today", "Energie erzeugt", "kWh", 0.01, "input_32", "Statistik Heute", "energy", "total_increasing"),
    (0x3304, "cons_today", "Energie verbraucht", "kWh", 0.01, "input_32", "Statistik Heute", "energy", "total_increasing"),
    (0x3300, "pv_max_today", "Max PV-Spannung", "V", 0.01, "input", "Statistik Heute", "voltage", "measurement"),
    
    # --- Kategorie: Statistik Gesamt ---
    (0x3312, "energy_total", "Energie erzeugt Ges.", "kWh", 0.01, "input_32", "Statistik Gesamt", "energy", "total_increasing"),
    (0x330A, "cons_total", "Energie verbraucht Ges.", "kWh", 0.01, "input_32", "Statistik Gesamt", "energy", "total_increasing"),
    
    # --- Kategorie: Konfiguration ---
    (0x9001, "bat_capacity", "Batteriekapazität", "Ah", 1, "holding", "Konfiguration", None, None),
    (0x9003, "limit_voltage", "Ladespannung Limit", "V", 0.01, "holding", "Konfiguration", "voltage", None),
    
    # --- Zeitstempel (Mit Sekunden für präzise Kontrolle) ---
    (None, "last_sync", "Letzte Aktualisierung", None, None, None, "Echtzeit", None, None),
]

def run():
    client = ModbusTcpClient(EPEVER_HOST, port=EPEVER_PORT)
    if not client.connect():
        print("FEHLER: Verbindung zum EPEVER nicht möglich.")
        return

    # Daten auslesen
    r3100 = client.read_input_registers(0x3100, 20, slave=SLAVE_ID).registers
    soc_val = client.read_input_registers(0x311A, 1, slave=SLAVE_ID).registers[0]
    r3300 = client.read_input_registers(0x3300, 20, slave=SLAVE_ID).registers
    r9000 = client.read_holding_registers(0x9000, 10, slave=SLAVE_ID).registers
    client.close()

    # Zeitstempel mit SEKUNDEN
    now_str = datetime.now().strftime("%H:%M:%S (%d.%m.)")

    # Shell-Ausgabe
    print(f"\n{'--- ECHTZEITDATEN ---':<30}")
    print(f"Update-Zeit:          {now_str}")
    print(f"Batterie-SOC:         {soc_val:>8} %")

    if len(sys.argv) > 1 and sys.argv[1] == "Sync2HA":
        payload = {
            "pv_voltage": r3100[0]/100.0, "pv_current": r3100[1]/100.0, "pv_power": decode_32bit(r3100[2], r3100[3])/100.0,
            "bat_voltage": r3100[4]/100.0, "charge_current": r3100[5]/100.0, "charge_power": decode_32bit(r3100[6], r3100[7])/100.0,
            "load_voltage": r3100[12]/100.0, "load_current": r3100[13]/100.0, "load_power": decode_32bit(r3100[14], r3100[15])/100.0,
            "bat_temp": r3100[16]/100.0, "dev_temp": r3100[17]/100.0, "bat_soc": soc_val,
            "energy_today": decode_32bit(r3300[12], r3300[13])/100.0, "cons_today": decode_32bit(r3300[4], r3300[5])/100.0,
            "pv_max_today": r3300[0]/100.0,
            "energy_total": decode_32bit(r3300[18], r3300[19])/100.0, "cons_total": decode_32bit(r3300[10], r3300[11])/100.0,
            "bat_capacity": r9000[1], "limit_voltage": r9000[3]/100.0,
            "last_sync": now_str
        }

        mq = mqtt.Client()
        if MQTT_USER: mq.username_pw_set(MQTT_USER, MQTT_PASS)
        mq.connect(MQTT_SERVER, MQTT_PORT)
        
        dev_info = {"identifiers": [DEVICE_ID], "name": "EPEVER XTRA-N 3210", "model": "XTRA-N", "manufacturer": "EPEVER"}
        
        for addr, sid, name, unit, factor, r_type, cat, d_class, s_class in SENSORS:
            config = {
                "name": f"{cat} {name}",
                "state_topic": f"{DEVICE_ID}/state",
                "value_template": f"{{{{ value_json.{sid} }}}}",
                "unique_id": f"{DEVICE_ID}_{sid}",
                "device": dev_info
            }
            if unit: config["unit_of_measurement"] = unit
            if d_class: config["device_class"] = d_class
            if s_class: config["state_class"] = s_class
            if cat == "Konfiguration": config["entity_category"] = "diagnostic"
            
            mq.publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{sid}/config", json.dumps(config), retain=True)

        mq.publish(f"{DEVICE_ID}/state", json.dumps(payload))
        mq.disconnect()
        print(f"[LOG] Daten & Zeit ({now_str}) erfolgreich an HA gesendet.")

if __name__ == "__main__":
    run()
