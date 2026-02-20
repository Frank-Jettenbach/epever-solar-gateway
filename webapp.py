#!/usr/bin/env python3
"""
EPEVER Web Interface - Flask Application
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request
from epever_controller import EpeverController, BATTERY_TYPES, LOAD_MODES, CHARGING_STATES

app = Flask(__name__)
app.config['SECRET_KEY'] = 'epever-secret-key-change-in-production'
app.config['APPLICATION_ROOT'] = '/epever'

EPEVER_HOST = os.environ.get('EPEVER_HOST', '192.168.178.150')
EPEVER_PORT = int(os.environ.get('EPEVER_PORT', 8899))

def get_controller():
    ctrl = EpeverController(EPEVER_HOST, EPEVER_PORT)
    return ctrl

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    ctrl = get_controller()
    if not ctrl.connect():
        return jsonify({"error": "Keine Verbindung zum EPEVER"}), 500
    try:
        data = ctrl.get_all_data()
        return jsonify(data)
    finally:
        ctrl.disconnect()

@app.route('/api/realtime')
def api_realtime():
    ctrl = get_controller()
    if not ctrl.connect():
        return jsonify({"error": "Keine Verbindung"}), 500
    try:
        return jsonify(ctrl.get_realtime_data())
    finally:
        ctrl.disconnect()

@app.route('/api/statistics')
def api_statistics():
    ctrl = get_controller()
    if not ctrl.connect():
        return jsonify({"error": "Keine Verbindung"}), 500
    try:
        return jsonify(ctrl.get_statistics())
    finally:
        ctrl.disconnect()

@app.route('/api/settings')
def api_settings():
    ctrl = get_controller()
    if not ctrl.connect():
        return jsonify({"error": "Keine Verbindung"}), 500
    try:
        return jsonify(ctrl.get_settings())
    finally:
        ctrl.disconnect()

@app.route('/api/settings/<int:register>', methods=['POST'])
def api_set_setting(register):
    ctrl = get_controller()
    if not ctrl.connect():
        return jsonify({"error": "Keine Verbindung"}), 500
    try:
        data = request.get_json()
        value = data.get('value')
        if value is None:
            return jsonify({"error": "Kein Wert angegeben"}), 400
        
        if ctrl.set_setting(register, int(value)):
            return jsonify({"success": True, "register": register, "value": value})
        else:
            return jsonify({"error": "Schreiben fehlgeschlagen"}), 500
    finally:
        ctrl.disconnect()

@app.route('/api/battery-types')
def api_battery_types():
    return jsonify(BATTERY_TYPES)

@app.route('/api/load-modes')
def api_load_modes():
    return jsonify(LOAD_MODES)

@app.route('/api/charging-states')
def api_charging_states():
    return jsonify(CHARGING_STATES)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=False)
