#!/usr/bin/env python3
"""
EPEVER XTRA-N / Tracer-AN Modbus Controller
Komplettes Auslesen aller Register und Schreiben von Einstellungen
"""

import sys
import time
import json
import argparse
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt

EPEVER_HOST = '192.168.178.150'
EPEVER_PORT = 8899
SLAVE_ID = 1

MQTT_SERVER = "192.168.178.57"
MQTT_PORT = 1883
MQTT_USER = "tasmota"
MQTT_PASS = "Tasmota01$"

DEVICE_ID = "epever_xtra3210"
DISCOVERY_PREFIX = "homeassistant"

def decode_32bit(low, high):
    return (high << 16) | low

def decode_signed_32bit(low, high):
    val = (high << 16) | low
    if val >= 0x80000000:
        val -= 0x100000000
    return val

BATTERY_TYPES = {0: "Sealed", 1: "GEL", 2: "Flooded", 3: "User", 4: "LFP", 5: "Li-NMC"}
CHARGING_STATES = {0: "Deaktiviert", 1: "Aktiv", 2: "MPPT", 3: "Equalize", 4: "Boost", 5: "Float", 6: "Current Limiting"}
LOAD_MODES = {
    0: "Manual", 1: "Light ON/OFF", 2: "Light ON+Timer", 3: "Time Control",
    4: "Test Mode", 5: "Morning ON", 17: "Street Light (Dusk-Dawn)"
}

REALTIME_INPUTS = [
    (0x3100, "pv_voltage", "PV-Spannung", "V", 0.01, "voltage"),
    (0x3101, "pv_current", "PV-Strom", "A", 0.01, "current"),
    (0x3102, "pv_power", "PV-Leistung", "W", 0.01, "power", True),
    (0x3104, "bat_voltage", "Batterie-Spannung", "V", 0.01, "voltage"),
    (0x3105, "charge_current", "Lade-Strom", "A", 0.01, "current"),
    (0x3106, "charge_power", "Lade-Leistung", "W", 0.01, "power", True),
    (0x310C, "load_voltage", "Last-Spannung", "V", 0.01, "voltage"),
    (0x310D, "load_current", "Last-Strom", "A", 0.01, "current"),
    (0x310E, "load_power", "Last-Leistung", "W", 0.01, "power", True),
    (0x3110, "bat_temp", "Batterie-Temp", "°C", 0.01, "temperature"),
    (0x3111, "dev_temp", "Geräte-Temp", "°C", 0.01, "temperature"),
    (0x311A, "bat_soc", "Batterie-SOC", "%", 1, "battery"),
    (0x311B, "bat_soh", "Batterie-SOH", "%", 1, "battery"),
    (0x311D, "charging_state", "Ladezustand", None, 1, None),
]

STATISTICS_INPUTS = [
    (0x3300, "pv_max_today", "Max PV-Spannung heute", "V", 0.01),
    (0x3301, "bat_min_today", "Min Bat-Spannung heute", "V", 0.01),
    (0x3302, "bat_max_today", "Max Bat-Spannung heute", "V", 0.01),
    (0x3304, "consumption_today", "Verbrauch heute", "kWh", 0.01, True),
    (0x330A, "consumption_total", "Verbrauch gesamt", "kWh", 0.01, True),
    (0x330C, "generation_today", "Erzeugung heute", "kWh", 0.01, True),
    (0x330E, "generation_month", "Erzeugung Monat", "kWh", 0.01, True),
    (0x3312, "generation_total", "Erzeugung gesamt", "kWh", 0.01, True),
    (0x3314, "co2_saved", "CO2-Ersparnis", "kg", 0.01, True),
    (0x3316, "running_hours", "Betriebsstunden", "h", 1),
]

SETTINGS_HOLDINGS = [
    (0x9000, "bat_type", "Batterietyp", None, 1, "list", list(BATTERY_TYPES.values())),
    (0x9001, "bat_capacity", "Batteriekapazitaet", "Ah", 1, "number", [1, 2000]),
    (0x9002, "temp_comp", "Temp-Kompensation", "mV/°C/2V", 1, "number", [0, 100]),
    (0x9003, "high_volt_disconnect", "HVD - Ueberspannung", "V", 0.01, "number", [10, 60]),
    (0x9004, "charging_limit_volt", "Ladelimit Spannung", "V", 0.01, "number", [10, 60]),
    (0x9005, "over_volt_reconnect", "Ueberspannung Wiedereinschalt", "V", 0.01, "number", [10, 60]),
    (0x9006, "equalize_volt", "Equalize Spannung", "V", 0.01, "number", [10, 60]),
    (0x9007, "boost_volt", "Boost Spannung", "V", 0.01, "number", [10, 60]),
    (0x9008, "float_volt", "Float Spannung", "V", 0.01, "number", [10, 60]),
    (0x9009, "low_volt_disconnect", "LVD - Tiefentladung", "V", 0.01, "number", [8, 50]),
    (0x900A, "under_volt_warning", "Unterspannung Warnung", "V", 0.01, "number", [8, 50]),
    (0x900B, "low_volt_reconnect", "Unterspannung Wiedereinschalt", "V", 0.01, "number", [8, 50]),
    (0x900C, "boost_reconnect_volt", "Boost Wiedereinschalt", "V", 0.01, "number", [8, 50]),
    (0x9013, "boost_duration", "Boost Dauer", "min", 1, "number", [10, 180]),
    (0x9014, "equalize_duration", "Equalize Dauer", "min", 1, "number", [0, 300]),
    (0x903D, "load_mode", "Last-Modus", None, 1, "list", list(LOAD_MODES.values())),
    (0x903E, "light_on_delay", "Licht AN Verzoegerung", "min", 1, "number", [0, 999]),
    (0x903F, "light_off_delay", "Licht AUS Verzoegerung", "min", 1, "number", [0, 999]),
    (0x9042, "load_timer1", "Last Timer 1", "min", 1, "number", [0, 1439]),
    (0x904E, "load_timer2", "Last Timer 2", "min", 1, "number", [0, 1439]),
    (0x9065, "device_address", "Geraeteadresse", None, 1, "number", [1, 255]),
    (0x906E, "bat_recognition", "Batterie-Erkennung", None, 1, "number", [0, 9]),
]

DEVICE_INFO_INPUTS = [
    (0x3000, "max_pv_volt", "Max PV-Spannung (Rated)", "V", 0.01),
    (0x3004, "rated_current", "Nennstrom", "A", 0.01),
]


class EpeverController:
    def __init__(self, host=EPEVER_HOST, port=EPEVER_PORT, slave_id=SLAVE_ID):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.client = None

    def connect(self):
        self.client = ModbusTcpClient(self.host, port=self.port)
        return self.client.connect()

    def disconnect(self):
        if self.client:
            self.client.close()

    def read_input(self, addr, count=1):
        result = self.client.read_input_registers(addr, count, slave=self.slave_id)
        if hasattr(result, 'registers') and len(result.registers) == count:
            return result.registers
        return None

    def read_holding(self, addr, count=1):
        result = self.client.read_holding_registers(addr, count, slave=self.slave_id)
        if hasattr(result, 'registers') and len(result.registers) == count:
            return result.registers
        return None

    def write_holding(self, addr, value):
        result = self.client.write_register(addr, value, slave=self.slave_id)
        return not result.isError() if hasattr(result, 'isError') else True

    def get_realtime_data(self):
        data = {}
        regs_3100 = self.read_input(0x3100, 20)
        if regs_3100 and len(regs_3100) >= 18:
            data["pv_voltage"] = regs_3100[0] * 0.01
            data["pv_current"] = regs_3100[1] * 0.01
            data["pv_power"] = decode_32bit(regs_3100[2], regs_3100[3]) * 0.01
            data["bat_voltage"] = regs_3100[4] * 0.01
            data["charge_current"] = regs_3100[5] * 0.01
            data["charge_power"] = decode_32bit(regs_3100[6], regs_3100[7]) * 0.01
            data["load_voltage"] = regs_3100[12] * 0.01
            data["load_current"] = regs_3100[13] * 0.01
            data["load_power"] = decode_32bit(regs_3100[14], regs_3100[15]) * 0.01
            data["bat_temp"] = regs_3100[16] * 0.01
            data["dev_temp"] = regs_3100[17] * 0.01

        soc_result = self.client.read_input_registers(0x311A, 1, slave=self.slave_id)
        if hasattr(soc_result, 'registers') and soc_result.registers:
            data["bat_soc"] = soc_result.registers[0]

        return data

    def get_statistics(self):
        data = {}
        regs = self.read_input(0x3300, 20)
        if regs and len(regs) >= 20:
            data["pv_max_today"] = regs[0] * 0.01
            data["bat_min_today"] = regs[1] * 0.01
            data["bat_max_today"] = regs[2] * 0.01
            data["consumption_today"] = decode_32bit(regs[4], regs[5]) * 0.01
            data["consumption_total"] = decode_32bit(regs[10], regs[11]) * 0.01
            data["generation_today"] = decode_32bit(regs[12], regs[13]) * 0.01
            data["generation_total"] = decode_32bit(regs[18], regs[19]) * 0.01
        return data

    def get_settings(self):
        data = {}
        
        # Battery settings 0x9000-0x900E (15 registers)
        regs_9000 = self.read_holding(0x9000, 15)
        if regs_9000 and len(regs_9000) >= 15:
            data["bat_type"] = BATTERY_TYPES.get(regs_9000[0], f"Unbekannt({regs_9000[0]})")
            data["bat_type_raw"] = regs_9000[0]
            data["bat_capacity"] = regs_9000[1]
            data["temp_comp"] = regs_9000[2]
            data["high_volt_disconnect"] = round(regs_9000[3] * 0.01, 2)
            data["charging_limit_volt"] = round(regs_9000[4] * 0.01, 2)
            data["over_volt_reconnect"] = round(regs_9000[5] * 0.01, 2)
            data["equalize_volt"] = round(regs_9000[6] * 0.01, 2)
            data["boost_volt"] = round(regs_9000[7] * 0.01, 2)
            data["float_volt"] = round(regs_9000[8] * 0.01, 2)
            data["low_volt_disconnect"] = round(regs_9000[9] * 0.01, 2)
            data["under_volt_warning"] = round(regs_9000[10] * 0.01, 2)
            data["low_volt_reconnect"] = round(regs_9000[11] * 0.01, 2)
            data["boost_reconnect_volt"] = round(regs_9000[12] * 0.01, 2)
            data["low_volt_disconnect_2"] = round(regs_9000[13] * 0.01, 2)
            data["under_volt_disconnect"] = round(regs_9000[14] * 0.01, 2)

        # Duration settings 0x9013-0x9017
        regs_9013 = self.read_holding(0x9013, 5)
        if regs_9013 and len(regs_9013) >= 5:
            data["boost_duration"] = regs_9013[0]
            data["equalize_duration"] = regs_9013[1]
            data["temp_comp_coeff"] = regs_9013[2]

        # Load settings 0x903D-0x903F, 0x9042-0x904D
        r = self.client.read_holding_registers(0x903D, 3, slave=self.slave_id)
        if hasattr(r, 'registers') and r.registers:
            data["load_mode"] = LOAD_MODES.get(r.registers[0], f"Unbekannt({r.registers[0]})")
            data["load_mode_raw"] = r.registers[0]
            data["light_on_delay"] = r.registers[1]
            data["light_off_delay"] = r.registers[2]

        return data

    def set_setting(self, register, value):
        return self.write_holding(register, int(value))

    def get_all_data(self):
        def round2(val):
            return round(val, 2) if isinstance(val, float) else val
        
        def round_dict(d):
            return {k: round2(v) if isinstance(v, float) else v for k, v in d.items()}
        
        return {
            "realtime": round_dict(self.get_realtime_data()),
            "statistics": round_dict(self.get_statistics()),
            "settings": round_dict(self.get_settings()),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


def print_data(data, title=""):
    if title:
        print(f"\n{'='*50}")
        print(f"  {title}")
        print(f"{'='*50}")
    for key, value in data.items():
        if isinstance(value, float):
            print(f"  {key:25s}: {value:.2f}")
        else:
            print(f"  {key:25s}: {value}")


def send_to_mqtt(data):
    mq = mqtt.Client()
    if MQTT_USER:
        mq.username_pw_set(MQTT_USER, MQTT_PASS)
    mq.connect(MQTT_SERVER, MQTT_PORT)

    dev_info = {
        "identifiers": [DEVICE_ID],
        "name": "EPEVER XTRA-N 3210",
        "model": "XTRA-N",
        "manufacturer": "EPEVER"
    }

    all_sensors = []
    
    for addr, sid, name, unit, factor, *rest in REALTIME_INPUTS:
        is_32bit = rest[0] if rest else False
        all_sensors.append((addr, sid, name, unit, factor, "Echtzeit", rest[1] if len(rest) > 1 else None, "measurement" if is_32bit else None, is_32bit))
    
    for addr, sid, name, unit, factor, *rest in STATISTICS_INPUTS:
        is_32bit = rest[0] if rest else False
        all_sensors.append((addr, sid, name, unit, factor, "Statistik", None, "total_increasing" if is_32bit else None, is_32bit))
    
    for item in SETTINGS_HOLDINGS:
        addr, sid, name, unit, factor, stype, srange = item[0], item[1], item[2], item[3], item[4], item[5], item[6]
        all_sensors.append((addr, sid, name, unit, factor, "Einstellungen", None, None, False))

    for item in all_sensors:
        addr, sid, name, unit, factor, cat, d_class, s_class, *_ = item
        
        config = {
            "name": f"{cat} {name}",
            "state_topic": f"{DEVICE_ID}/state",
            "value_template": f"{{{{ value_json.{sid} }}}}",
            "unique_id": f"{DEVICE_ID}_{sid}",
            "device": dev_info
        }
        if unit:
            config["unit_of_measurement"] = unit
        if d_class:
            config["device_class"] = d_class
        if s_class:
            config["state_class"] = s_class
        if cat == "Einstellungen":
            config["entity_category"] = "diagnostic"

        mq.publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{sid}/config", json.dumps(config), retain=True)

    payload = {
        **data["realtime"],
        **data["statistics"],
        **data["settings"],
        **data["device_info"],
        "last_update": data["last_update"]
    }

    mq.publish(f"{DEVICE_ID}/state", json.dumps(payload))
    mq.disconnect()
    print(f"\n[MQTT] Daten an Home Assistant gesendet ({data['last_update']})")


def interactive_mode(ctrl):
    while True:
        print("\n" + "="*60)
        print("  EPEVER KONTROLLPANEL")
        print("="*60)
        print("  1 - Alle Daten anzeigen")
        print("  2 - Echtzeitdaten")
        print("  3 - Statistiken")
        print("  4 - Einstellungen anzeigen")
        print("  5 - Einstellung aendern")
        print("  6 - An Home Assistant senden")
        print("  q - Beenden")
        print("="*60)
        
        choice = input("Auswahl: ").strip().lower()
        
        if choice == '1':
            data = ctrl.get_all_data()
            print_data(data["realtime"], "ECHTZEITDATEN")
            print_data(data["statistics"], "STATISTIK")
            print_data(data["settings"], "EINSTELLUNGEN")
            print_data(data["device_info"], "GERAETEINFO")
            
        elif choice == '2':
            print_data(ctrl.get_realtime_data(), "ECHTZEITDATEN")
            
        elif choice == '3':
            print_data(ctrl.get_statistics(), "STATISTIK")
            
        elif choice == '4':
            print_data(ctrl.get_settings(), "EINSTELLUNGEN")
            
        elif choice == '5':
            print("\nAenderbare Einstellungen:")
            for i, (addr, sid, name, unit, factor, stype, srange) in enumerate(SETTINGS_HOLDINGS):
                if stype == "list":
                    print(f"  {i+1:2d}. {name} (Optionen: {srange})")
                else:
                    print(f"  {i+1:2d}. {name} (Bereich: {srange[0]}-{srange[1]} {unit or ''})")
            
            try:
                idx = int(input("\nNummer der Einstellung: ")) - 1
                if 0 <= idx < len(SETTINGS_HOLDINGS):
                    addr, sid, name, unit, factor, stype, srange = SETTINGS_HOLDINGS[idx]
                    
                    if stype == "list":
                        print(f"\nVerfuegbare Optionen:")
                        for i, opt in enumerate(srange):
                            print(f"  {i}: {opt}")
                        val = int(input("Auswahl: "))
                    else:
                        val = float(input(f"Neuer Wert ({srange[0]}-{srange[1]} {unit or ''}): "))
                        if factor != 1:
                            val = int(val / factor)
                    
                    if ctrl.set_setting(addr, val):
                        print(f"\n[OK] {name} erfolgreich geaendert!")
                        time.sleep(0.5)
                        print_data(ctrl.get_settings(), "NEUE EINSTELLUNGEN")
                    else:
                        print(f"\n[FEHLER] Aenderung fehlgeschlagen!")
                else:
                    print("Ungueltige Auswahl!")
            except Exception as e:
                print(f"Fehler: {e}")
                
        elif choice == '6':
            data = ctrl.get_all_data()
            send_to_mqtt(data)
            
        elif choice == 'q':
            print("Beenden...")
            break


def main():
    parser = argparse.ArgumentParser(description="EPEVER XTRA-N Controller")
    parser.add_argument("--ip", default=EPEVER_HOST, help="IP-Adresse des EPEVER")
    parser.add_argument("--port", type=int, default=EPEVER_PORT, help="Modbus-Port")
    parser.add_argument("--set", nargs=2, metavar=("REGISTER", "VALUE"), help="Register setzen (hex oder dezimal)")
    parser.add_argument("--read", metavar="REGISTER", help="Register lesen (hex oder dezimal)")
    parser.add_argument("--mqtt", action="store_true", help="Daten an MQTT senden")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interaktiver Modus")
    args = parser.parse_args()

    ctrl = EpeverController(args.ip, args.port)
    
    if not ctrl.connect():
        print("FEHLER: Keine Verbindung zum EPEVER!")
        sys.exit(1)

    try:
        if args.set:
            reg = int(args.set[0], 0)
            val = int(args.set[1], 0)
            if ctrl.set_setting(reg, val):
                print(f"[OK] Register 0x{reg:04X} = {val}")
            else:
                print(f"[FEHLER] Schreiben fehlgeschlagen!")
                
        elif args.read:
            reg = int(args.read, 0)
            result = ctrl.read_holding(reg)
            if result:
                print(f"Register 0x{reg:04X} = {result[0]} (0x{result[0]:04X})")
            else:
                print(f"[FEHLER] Lesen fehlgeschlagen!")
                
        elif args.mqtt:
            data = ctrl.get_all_data()
            if args.json:
                print(json.dumps(data, indent=2))
            send_to_mqtt(data)
            
        elif args.json:
            print(json.dumps(ctrl.get_all_data(), indent=2))
            
        elif args.interactive:
            interactive_mode(ctrl)
            
        else:
            data = ctrl.get_all_data()
            print_data(data["realtime"], "ECHTZEITDATEN")
            print_data(data["statistics"], "STATISTIK")
            print_data(data["settings"], "EINSTELLUNGEN")
            print_data(data["device_info"], "GERAETEINFO")

    finally:
        ctrl.disconnect()


if __name__ == "__main__":
    main()
