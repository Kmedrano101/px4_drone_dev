"""Consola NuttX del PX4 por MAVLink SERIAL_CONTROL (device 10 = SHELL)."""
import sys, time
import fc
from pymavlink import mavutil

DEV_SHELL = 10
FLAGS = (mavutil.mavlink.SERIAL_CONTROL_FLAG_RESPOND
         | mavutil.mavlink.SERIAL_CONTROL_FLAG_EXCLUSIVE
         | mavutil.mavlink.SERIAL_CONTROL_FLAG_MULTI)

def send(m, data: bytes):
    while data:
        chunk, data = data[:70], data[70:]
        m.mav.serial_control_send(DEV_SHELL, FLAGS, 0, 0, len(chunk),
                                  chunk.ljust(70, b'\x00'))

def pump(m, seconds):
    out = b''
    t0 = time.time()
    while time.time() - t0 < seconds:
        m.mav.serial_control_send(DEV_SHELL, FLAGS, 0, 0, 0, b'\x00' * 70)
        msg = m.recv_match(type='SERIAL_CONTROL', blocking=True, timeout=0.2)
        if msg and msg.count:
            out += bytes(msg.data[:msg.count])
    return out.decode('utf-8', 'replace')

def run(m, cmd, wait=2.5):
    send(m, (cmd + '\n').encode())
    return pump(m, wait)

if __name__ == '__main__':
    m = fc.connect()
    pump(m, 0.5)
    for cmd in sys.argv[1:]:
        print(f"\n=========== nsh> {cmd}")
        print(run(m, cmd, wait=3.0))
