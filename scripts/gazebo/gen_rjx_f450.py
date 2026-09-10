#!/usr/bin/env python3
"""Genera rjx_f450_base/model.sdf con las medidas reales de PLATAFORMA_HARDWARE.md."""
import math
import os

M = "/home/kmedrano/PX4-Autopilot/Tools/simulation/gz/models"
R_MOT = 0.225                      # 450 mm de diagonal
A = R_MOT / math.sqrt(2)           # 0.1591
Z_ARM, Z_ROTOR, Z_GUARD = 0.016, 0.062, 0.052
ROTORS = [(A, -A), (-A, A), (A, A), (-A, -A)]

# Desglose de masa (PLATAFORMA_HARDWARE.md):
#   frame ~280 + 4x motor 46.6 (186) + ESC 13.5 + FC 6.5 + bateria 222
#   + RPi4 46 + ventilador/soportes 30 + MTF-01P 8 + D500 50
#   + 4x protector impreso ~30 (120) + helices 24 + cableado 80 = ~1.07 kg
MASS = 1.2
IXX = IYY = MASS * (0.40**2 + 0.12**2) / 12
IZZ = MASS * (0.40**2 + 0.40**2) / 12

CARBON = "0.07 0.07 0.08"
RED    = "0.72 0.06 0.09"
GREEN  = "0.05 0.32 0.11"
BEIGE  = "0.85 0.78 0.60"
DARK   = "0.12 0.12 0.13"
ORANGE = "0.90 0.33 0.05"


def mat(rgb, spec="0.1 0.1 0.1"):
    return ("        <material>\n"
            f"          <ambient>{rgb} 1</ambient>\n"
            f"          <diffuse>{rgb} 1</diffuse>\n"
            f"          <specular>{spec} 1</specular>\n"
            "        </material>\n")


def box(n, p, s, c, sp="0.1 0.1 0.1"):
    return (f'      <visual name="{n}">\n        <pose>{p}</pose>\n'
            f"        <geometry><box><size>{s}</size></box></geometry>\n"
            f"{mat(c, sp)}      </visual>\n")


def cyl(n, p, r, l, c, sp="0.1 0.1 0.1"):
    return (f'      <visual name="{n}">\n        <pose>{p}</pose>\n'
            f"        <geometry><cylinder><radius>{r}</radius><length>{l}</length></cylinder></geometry>\n"
            f"{mat(c, sp)}      </visual>\n")


# --- sensores de base que PX4 exige (topics fijos en GZBridge.cpp) ---
#   imu_sensor       -> /link/base_link/sensor/imu_sensor/imu   (OBLIGATORIO, linea 218)
#   air_pressure     -> barometro
#   magnetometer     -> el dron real NO lleva; se deja para que la sim vuele,
#                       se apaga con SYS_HAS_MAG=0 (ver doc SIMULACION_GAZEBO_INDOOR.md)
#   navsat           -> GPS, desactivado por airframe con SYS_HAS_GPS=0
BASE_SENSORS = open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_sensors.xml")
).read()

v = []
v.append(box("plate_bottom", "0 0 0 0 0 0", "0.16 0.16 0.0025", CARBON, "0.25 0.25 0.25"))
v.append(box("plate_top", "0 0 0.032 0 0 0", "0.155 0.155 0.002", CARBON, "0.25 0.25 0.25"))
# ESC 4-en-1 MicoAir Bluejay-60A: 44 x 43.5 x 5.2 mm
v.append(box("esc_4in1", "0 0 0.0075 0 0 0", "0.044 0.0435 0.0052", "0.09 0.09 0.10", "0.2 0.2 0.2"))
# FC NxtPX4v2: 27 x 32 x 8 mm
v.append(box("fc_nxtpx4v2", "0 0 0.0385 0 0 0", "0.032 0.027 0.008", "0.10 0.10 0.11", "0.2 0.2 0.2"))

for i, (x, y) in enumerate(ROTORS):
    yaw = math.atan2(y, x)
    r0, r1 = 0.030, R_MOT
    rm = (r0 + r1) / 2
    v.append(cyl(f"arm_{i}",
                 f"{rm*math.cos(yaw):.4f} {rm*math.sin(yaw):.4f} {Z_ARM} 0 1.5708 {yaw:.4f}",
                 0.008, r1 - r0, CARBON, "0.2 0.2 0.2"))
    # T-Motor F90 2806.5: campana 33.4 mm de diametro, 34.7 mm de alto
    v.append(cyl(f"motor_{i}", f"{x:.4f} {y:.4f} 0.0425 0 0 0", 0.0167, 0.0247, DARK, "0.4 0.4 0.4"))
    v.append(cyl(f"motor_bell_{i}", f"{x:.4f} {y:.4f} 0.0565 0 0 0", 0.0167, 0.0100, "0.20 0.20 0.22", "0.5 0.5 0.5"))
    v.append(cyl(f"motor_shaft_{i}", f"{x:.4f} {y:.4f} 0.0635 0 0 0", 0.002, 0.006, "0.6 0.6 0.62", "0.7 0.7 0.7"))
    v.append(f'      <visual name="prop_guard_{i}">\n'
             f"        <pose>{x:.4f} {y:.4f} {Z_GUARD} 0 0 {yaw:.4f}</pose>\n"
             "        <geometry><mesh>\n"
             "          <uri>model://rjx_f450_base/meshes/prop_guard.stl</uri>\n"
             "          <scale>0.001 0.001 0.001</scale>\n"
             "        </mesh></geometry>\n"
             f"{mat(RED, '0.15 0.05 0.05')}      </visual>\n")

# --- tren de aterrizaje: dos patines en T invertida (como el dron real) ---
#   patin horizontal de tubo corriendo adelante-atras + dos montantes por lado.
#   Visto de frente cada lado es una T invertida.
SKID_Y, SKID_Z, SKID_L = 0.105, -0.160, 0.280
for s_i, sy in enumerate([1, -1]):
    # patin horizontal (tubo a lo largo de X)
    v.append(cyl(f"skid_{s_i}", f"0 {SKID_Y*sy:.4f} {SKID_Z} 0 1.5708 0",
                 0.009, SKID_L, CARBON, "0.2 0.2 0.2"))
    # tapas redondeadas de los extremos
    for e_i, ex in enumerate([1, -1]):
        v.append(cyl(f"skid_{s_i}_cap_{e_i}",
                     f"{SKID_L/2*ex:.4f} {SKID_Y*sy:.4f} {SKID_Z} 0 1.5708 0",
                     0.0105, 0.012, DARK))
    # UN solo montante por patin, centrado -> visto de frente es una T invertida
    y0, y1 = 0.055 * sy, SKID_Y * sy
    z0, z1 = -0.002, SKID_Z
    dy, dz = y1 - y0, z1 - z0
    L = math.sqrt(dy * dy + dz * dz)
    v.append(cyl(f"strut_{s_i}",
                 f"0 {(y0+y1)/2:.4f} {(z0+z1)/2:.4f} {math.atan2(dy, -dz):.4f} 0 0",
                 0.009, L, CARBON, "0.2 0.2 0.2"))

# Ovonic 6S1P 1300 mAh: 74 x 44 x 34 mm, 222 g
v.append(box("battery", "0 0 -0.030 0 0 0", "0.074 0.044 0.034", "0.10 0.10 0.12", "0.05 0.05 0.05"))
v.append(box("battery_holder", "0 0 -0.050 0 0 0", "0.080 0.050 0.020", ORANGE))

for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
    v.append(cyl(f"standoff_{i}", f"{0.039*sx:.4f} {0.024*sy:.4f} 0.047 0 0 0",
                 0.0025, 0.028, "0.6 0.6 0.62", "0.5 0.5 0.5"))
v.append(box("rpi4_pcb", "0 0 0.0635 0 0 0", "0.085 0.056 0.0016", GREEN, "0.15 0.2 0.15"))
v.append(box("rpi4_usb", "0.036 0.016 0.0705 0 0 0", "0.017 0.030 0.013", "0.55 0.55 0.58", "0.5 0.5 0.5"))
v.append(box("rpi4_eth", "0.036 -0.018 0.0705 0 0 0", "0.021 0.016 0.014", "0.50 0.50 0.53", "0.5 0.5 0.5"))
v.append(box("rpi4_soc", "-0.005 0 0.0665 0 0 0", "0.015 0.015 0.0022", "0.15 0.15 0.16"))
for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
    v.append(cyl(f"standoff_hi_{i}", f"{0.039*sx:.4f} {0.024*sy:.4f} 0.081 0 0 0",
                 0.0025, 0.030, "0.6 0.6 0.62", "0.5 0.5 0.5"))
v.append(box("deck_plate", "0 0 0.0975 0 0 0", "0.098 0.072 0.004", BEIGE, "0.08 0.08 0.08"))
v.append(cyl("rpi4_fan", "0.012 0 0.0755 0 0 0", 0.0145, 0.010, "0.12 0.12 0.13", "0.2 0.2 0.2"))


def rotor(i, x, y):
    blades = ""
    for b in range(3):                      # HQProp 7x4x3, tripala
        ang = b * 2 * math.pi / 3
        blades += (f'      <visual name="rotor_{i}_blade_{b}">\n'
                   f"        <pose>{0.048*math.cos(ang):.4f} {0.048*math.sin(ang):.4f} 0 0 0.06 {ang:.4f}</pose>\n"
                   "        <geometry><box><size>0.081 0.017 0.0016</size></box></geometry>\n"
                   f"{mat('0.24 0.26 0.20', '0.15 0.15 0.15')}      </visual>\n")
    return (f'    <link name="rotor_{i}">\n      <gravity>true</gravity>\n'
            "      <self_collide>false</self_collide>\n      <velocity_decay/>\n"
            f"      <pose>{x:.4f} {y:.4f} {Z_ROTOR} 0 0 0</pose>\n"
            "      <inertial>\n        <mass>0.0095</mass>\n        <inertia>\n"
            "          <ixx>2.1e-07</ixx><ixy>0</ixy><ixz>0</ixz>\n"
            "          <iyy>1.05e-05</iyy><iyz>0</iyz><izz>1.07e-05</izz>\n"
            "        </inertia>\n      </inertial>\n"
            f'      <visual name="rotor_{i}_hub">\n'
            "        <geometry><cylinder><radius>0.008</radius><length>0.006</length></cylinder></geometry>\n"
            f"{mat('0.15 0.15 0.16')}      </visual>\n{blades}"
            f'      <collision name="rotor_{i}_collision">\n'
            "        <geometry><box><size>0.1778 0.017 0.0016</size></box></geometry>\n"
            "        <surface><contact><ode><min_depth>0.001</min_depth><max_vel>0</max_vel></ode></contact>"
            "<friction><ode/></friction></surface>\n      </collision>\n    </link>\n"
            f'    <joint name="rotor_{i}_joint" type="revolute">\n'
            f"      <parent>base_link</parent>\n      <child>rotor_{i}</child>\n"
            "      <axis>\n        <xyz>0 0 1</xyz>\n"
            "        <limit><lower>-1e+16</lower><upper>1e+16</upper></limit>\n"
            "        <dynamics><spring_reference>0</spring_reference><spring_stiffness>0</spring_stiffness></dynamics>\n"
            "      </axis>\n    </joint>\n")


col = ('      <collision name="body_collision">\n        <pose>0 0 0.02 0 0 0</pose>\n'
       "        <geometry><box><size>0.17 0.17 0.10</size></box></geometry>\n      </collision>\n"
       '      <collision name="battery_collision">\n        <pose>0 0 -0.035 0 0 0</pose>\n'
       "        <geometry><box><size>0.078 0.050 0.050</size></box></geometry>\n      </collision>\n")
for i, (x, y) in enumerate(ROTORS):
    # el arco va centrado en el eje del motor y llega a r=0.10 -> footprint 0.325 m
    col += (f'      <collision name="guard_{i}_collision">\n'
            f"        <pose>{x:.4f} {y:.4f} {Z_GUARD} 0 0 {math.atan2(y,x):.4f}</pose>\n"
            "        <geometry><box><size>0.20 0.20 0.065</size></box></geometry>\n      </collision>\n")
for s_i, sy in enumerate([1, -1]):
    col += (f'      <collision name="skid_{s_i}_collision">\n'
            f"        <pose>0 {SKID_Y*sy:.4f} {SKID_Z} 0 1.5708 0</pose>\n"
            f"        <geometry><cylinder><radius>0.009</radius><length>{SKID_L}</length></cylinder></geometry>\n"
            "        <surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface>\n"
            "      </collision>\n")

sdf = ('<?xml version="1.0" encoding="UTF-8"?>\n<!--\n'
       "  RJX F450 carbono - recreacion del drone real de pruebas indoor.\n"
       "  Medidas y masas de docs/PLATAFORMA_HARDWARE.md:\n"
       "    frame RJX F450, 450 mm de diagonal -> rotores a +-0.159 m\n"
       "    T-Motor F90 2806.5 1300KV: 33.4 x 34.7 mm, 46.6 g, 2360 g de empuje con 7x4\n"
       "    HQProp 7x4x3 tripala\n"
       "    ESC MicoAir Bluejay-4IN1-60A: 44 x 43.5 x 5.2 mm\n"
       "    FC NxtPX4v2: 27 x 32 x 8 mm\n"
       "    Bateria Ovonic 6S1P 1300 mAh: 74 x 44 x 34 mm, 222 g\n"
       "    Protectores impresos: malla real jaula_sin_patas.stl, arco de 100 mm de radio\n"
       f"  AUW modelada: {MASS} kg. Los sensores van en rjx_f450_indoor.\n-->\n"
       "<sdf version='1.9'>\n  <model name='rjx_f450_base'>\n"
       "    <self_collide>false</self_collide>\n"
       '    <link name="base_link">\n      <inertial>\n'
       f"        <mass>{MASS}</mass>\n        <inertia>\n"
       f"          <ixx>{IXX:.6f}</ixx><ixy>0</ixy><ixz>0</ixz>\n"
       f"          <iyy>{IYY:.6f}</iyy><iyz>0</iyz><izz>{IZZ:.6f}</izz>\n"
       "        </inertia>\n      </inertial>\n"
       "      <gravity>true</gravity>\n      <velocity_decay/>\n"
       + col + "".join(v) + BASE_SENSORS + "    </link>\n"
       + "".join(rotor(i, x, y) for i, (x, y) in enumerate(ROTORS))
       + "  </model>\n</sdf>\n")

open(f"{M}/rjx_f450_base/model.sdf", "w").write(sdf)
print(f"masa {MASS} kg   ixx=iyy={IXX:.5f}   izz={IZZ:.5f}")
print(f"rotores a +-{A:.4f} m   {len(v)} visuales")
