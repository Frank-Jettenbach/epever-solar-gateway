#!/usr/bin/env python3
"""
EPEVER MQTT Service - Sendet Daten an Home Assistant

Kann als Standalone-Script oder als Service laufen:
    python mqtt_service.py              # Einmalig senden
    python mqtt_service.py --daemon     # Als Daemon (alle 60s)
    python mqtt_service.py --interval 30  # Alle 30 Sekunden
"""

import os
import sys
import json
import time
import signal
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paho.mqtt.client as mqtt
from epever_controller import EpeverController, BATTERY_TYPES, LOAD_MODES

# Konfiguration aus Umgebungsvariablen oder Defaults
EPEVER_HOST = os.environ.get('EPEVER_HOST', '192.168.178.150')
EPEVER_PORT = int(os.environ.get('EPEVER_PORT', 8899))
SLAVE_ID = int(os.environ.get('EPEVER_SLAVE_ID', 1))

MQTT_SERVER = os.environ.get('MQTT_SERVER', '192.168.178.57')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
MQTT_USER = os.environ.get('MQTT_USER', 'tasmota')
MQTT_PASS = os.environ.get('MQTT_PASS', 'Tasmota01$')

DEVICE_ID = os.environ.get('DEVICE_ID', 'epever_xtra3210')
DISCOVERY_PREFIX = os.environ.get('DISCOVERY_PREFIX', 'homeassistant')

DEVICE_INFO = {
    "identifiers": [DEVICE_ID],
    "name": "EPEVER XTRA-N 3210",
    "model": "XTRA-N",
    "manufacturer": "EPEVER"
}

SENSOR_DEFINITIONS = [
    ("pv_voltage", "PV Spannung", "V", "voltage", "measurement"),
    ("pv_current", "PV Strom", "A", "current", "measurement"),
    ("pv_power", "PV Leistung", "W", "power", "measurement"),
    ("bat_voltage", "Batterie Spannung", "V", "voltage", "measurement"),
    ("charge_current", "Ladestrom", "A", "current", "measurement"),
    ("charge_power", "Ladeleistung", "W", "power", "measurement"),
    ("load_voltage", "Last Spannung", "V", "voltage", "measurement"),
    ("load_current", "Last Strom", "A", "current", "measurement"),
    ("load_power", "Last Leistung", "W", "power", "measurement"),
    ("bat_temp", "Batterie Temperatur", "°C", "temperature", "measurement"),
    ("dev_temp", "Gerät Temperatur", "°C", "temperature", "measurement"),
    ("bat_soc", "Batterie SOC", "%", "battery", "measurement"),
    ("pv_max_today", "Max PV Spannung heute", "V", "voltage", "measurement"),
    ("bat_min_today", "Min Bat Spannung heute", "V", "voltage", "measurement"),
    ("bat_max_today", "Max Bat Spannung heute", "V", "voltage", "measurement"),
    ("consumption_today", "Verbrauch heute", "kWh", "energy", "total_increasing"),
    ("consumption_total", "Verbrauch gesamt", "kWh", "energy", "total_increasing"),
    ("generation_today", "Erzeugung heute", "kWh", "energy", "total_increasing"),
    ("generation_total", "Erzeugung gesamt", "kWh", "energy", "total_increasing"),
    ("bat_capacity", "Batteriekapazität", "Ah", None, None),
    ("bat_type", "Batterietyp", None, None, None),
    ("last_update", "Letzte Aktualisierung", None, "timestamp", None),
]

running = True

def signal_handler(sig, frame):
    global running
    running = False
    print("\nBeende Service...")

def publish_discovery(mq):
    for sid, name, unit, d_class, s_class in SENSOR_DEFINITIONS:
        config = {
            "name": name,
            "state_topic": f"{DEVICE_ID}/state",
            "value_template": f"{{{{ value_json.{sid} }}}}",
            "unique_id": f"{DEVICE_ID}_{sid}",
            "device": DEVICE_INFO
        }
        if unit:
            config["unit_of_measurement"] = unit
        if d_class:
            config["device_class"] = d_class
        if s_class:
            config["state_class"] = s_class
        
        topic = f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{sid}/config"
        mq.publish(topic, json.dumps(config), retain=True)

def send_to_mqtt(data):
    try:
        mq = mqtt.Client()
        if MQTT_USER:
            mq.username_pw_set(MQTT_USER, MQTT_PASS)
        mq.connect(MQTT_SERVER, MQTT_PORT, 60)
        
        publish_discovery(mq)
        
        payload = {
            **data["realtime"],
            **data["statistics"],
            **data["settings"],
            "last_sync": data["last_update"],
            "last_update": datetime.now().isoformat()
        }
        
        mq.publish(f"{DEVICE_ID}/state", json.dumps(payload))
        mq.disconnect()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Daten an HA gesendet - SOC: {data['realtime'].get('bat_soc', 'N/A')}%", flush=True)
        return True
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] MQTT Fehler: {e}", flush=True)
        return False

def run_once():
    ctrl = EpeverController(EPEVER_HOST, EPEVER_PORT, SLAVE_ID)
    if not ctrl.connect():
        print("FEHLER: Keine Verbindung zum EPEVER")
        return False
    
    try:
        data = ctrl.get_all_data()
        return send_to_mqtt(data)
    finally:
        ctrl.disconnect()

def run_daemon(interval=60):
    global running
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    ctrl = EpeverController(EPEVER_HOST, EPEVER_PORT, SLAVE_ID)
    
    print(f"EPEVER MQTT Service gestartet (Interval: {interval}s)")
    print(f"MQTT: {MQTT_SERVER}:{MQTT_PORT}")
    print(f"EPEVER: {EPEVER_HOST}:{EPEVER_PORT}")
    print()
    
    while running:
        if ctrl.connect():
            try:
                data = ctrl.get_all_data()
                send_to_mqtt(data)
            except Exception as e:
                print(f"Fehler: {e}")
            finally:
                ctrl.disconnect()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Keine Verbindung zum EPEVER")
        
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)
    
    print("Service beendet")

def main():
    parser = argparse.ArgumentParser(description="EPEVER MQTT Service")
    parser.add_argument("--daemon", "-d", action="store_true", help="Als Daemon laufen")
    parser.add_argument("--interval", "-i", type=int, default=60, help="Interval in Sekunden (default: 60)")
    parser.add_argument("--once", "-o", action="store_true", help="Einmalig senden und beenden")
    args = parser.parse_args()
    
    if args.daemon:
        run_daemon(args.interval)
    elif args.once:
        run_once()
    else:
        run_once()

if __name__ == "__main__":
    main()
