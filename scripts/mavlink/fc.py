"""Utilidades MAVLink minimas para hablar con el FC.

Puerto y velocidad por variables de entorno:
    cable USB : FC_DEV=/dev/ttyACM0  FC_BAUD=115200   (la velocidad da igual, es CDC)
    radio     : FC_DEV=/dev/ttyUSB0  FC_BAUD=57600    (= SER_TEL1_BAUD)
"""
import os, sys, time, struct
from pymavlink import mavutil

DEV  = os.environ.get('FC_DEV', '/dev/ttyACM0')
BAUD = int(os.environ.get('FC_BAUD', '115200'))

def connect(timeout=int(os.environ.get("FC_TIMEOUT", "45"))):
    """El USB del PX4 solo empieza a transmitir cuando recibe MAVLink: hay que
    mandarle heartbeats mientras se espera el suyo."""
    m = mavutil.mavlink_connection(DEV, baud=BAUD, source_system=250, source_component=190)
    t0 = time.time()
    while time.time() - t0 < timeout:
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=0.5)
        if hb is not None and hb.get_srcSystem() != 250:
            m.target_system = hb.get_srcSystem()
            m.target_component = hb.get_srcComponent()
            return m
    raise SystemExit("sin heartbeat")

def autopilot_version(m):
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION, 0,0,0,0,0,0)
    t0=time.time()
    while time.time()-t0 < 5:
        msg = m.recv_match(type='AUTOPILOT_VERSION', blocking=True, timeout=1)
        if msg: return msg
    return None

def param_get(m, name, timeout=5):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    t0=time.time()
    while time.time()-t0 < timeout:
        msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if msg and msg.param_id.strip('\x00') == name:
            return msg
    return None

def decode(msg):
    """PX4 mete los int32 bit a bit en el campo float."""
    if msg.param_type in (mavutil.mavlink.MAV_PARAM_TYPE_INT32,
                          mavutil.mavlink.MAV_PARAM_TYPE_UINT32,
                          mavutil.mavlink.MAV_PARAM_TYPE_INT16,
                          mavutil.mavlink.MAV_PARAM_TYPE_UINT16,
                          mavutil.mavlink.MAV_PARAM_TYPE_INT8,
                          mavutil.mavlink.MAV_PARAM_TYPE_UINT8):
        return struct.unpack('<i', struct.pack('<f', msg.param_value))[0]
    return msg.param_value

def encode(value, ptype):
    if ptype != mavutil.mavlink.MAV_PARAM_TYPE_REAL32:
        return struct.unpack('<f', struct.pack('<i', int(value)))[0]
    return float(value)
