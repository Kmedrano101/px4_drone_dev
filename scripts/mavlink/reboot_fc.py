#!/usr/bin/env python3
"""Reinicia el FC. ABORTA si el vehiculo esta armado.

Uso:  FC_DEV=/dev/ttyACM0 python3 reboot_fc.py
"""
import time
import fc
from pymavlink import mavutil

m = fc.connect()
hb = m.messages['HEARTBEAT']
if bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
    raise SystemExit("ABORTADO: el vehiculo esta ARMADO")
print("desarmado, reiniciando...")

m.mav.command_long_send(m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0, 1, 0, 0, 0, 0, 0, 0)
ack = m.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
print("ack:", ack.result if ack else "sin ack (normal: el FC ya se esta reiniciando)")
m.close()

time.sleep(15)
m = fc.connect(timeout=60)
print("reconectado: sys", m.target_system)
v = fc.autopilot_version(m)
if v:
    fv = v.flight_sw_version
    print("fw %d.%d.%d" % ((fv >> 24) & 0xff, (fv >> 16) & 0xff, (fv >> 8) & 0xff))
