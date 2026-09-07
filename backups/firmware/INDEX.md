# Índice de versiones de firmware — NxtPX4v2 (hkust_nxt-dual)

Base común: **PX4 commit `82e3322e`** (1.17.0 main). Todas las mods de board son **sin commitear**;
cada versión guarda su `board_config.diff` para reconstruirla exacta.

Repo de código: `/home/kmedrano/PX4-Autopilot`

> **⚠️ 2026-09-04 — el FC NO tiene ninguna de estas versiones.** Está con el firmware
> de fábrica **PX4 1.14.3** (branch `micoair743-v1.14.3`, build Nov 19 2024). Fue
> reflasheado con stock en algún momento después del 2026-07-23. Ver `v0-vendor_2026-09-04_stock-1.14.3/`.

## Versiones

| Versión | Binario | Estado | Descripción |
|---|---|---|---|
| **V0** stock | ❌ recreable | referencia | Board sin mods (git limpio + build) |
| **Original+mag** | ❌ recreable | ~la que voló bien | Stock + drivers mag (sin USART6/GPS3) |
| **V1** | ✅ `v1_2026-07-17_usart6gps3+mag/` | guardada | + USART6 sin consola + GPS3 (inútil) + mag |
| **V2** | ✅ `v2_2026-07-23_optimizada-AB/` | guardada | Revert USART6/GPS3 + optimización (quitar FW/VTOL/etc.) |
| **V0-vendor** | ❌ no extraíble | **EN EL FC ahora** | Firmware de fábrica PX4 1.14.3 (`micoair743-v1.14.3`) |

### Backups de parámetros

| Fecha | Archivo | Corresponde a |
|---|---|---|
| 2026-07-23 | `../backup_fc_2026-07-23.params` (967) | V1 / PX4 1.17.0 |
| 2026-09-04 | `../backup_fc_2026-09-04.params` (909) | V0-vendor / PX4 1.14.3 recién flasheado — **estado previo, punto de rollback** |
| 2026-09-04 | `../backup_fc_2026-09-04_post-migracion.params` (914) | V0-vendor + 97 params migrados desde el FC de 1.17 |

### Migración de params 1.17 → 1.14.3 (2026-09-04)

De los 967 params del FC de 1.17: **834** existen también en la 1.14.3, **133** no.
De esos 834 se migraron **97** (los 669 restantes ya eran idénticos). Excluidos a propósito:

| Excluido | Motivo |
|---|---|
| `CAL_*` (46) | Calibración **por unidad física**, no por modelo — recalibrar en este FC |
| `SENS_BOARD_X/Y_OFF` | Nivelación de horizonte, también por unidad |
| `SER_*`, `MAV_0/1/2_*`, `GPS_*_CONFIG` | La 1.14.3 del fabricante solo declara GPS1 y TEL1 |
| `RC_PORT_CONFIG` (→105) | Código de puerto inexistente aquí; mataría la entrada RC (queda en 300) |
| `UXRCE_DDS_CFG` (→102) | Apunta a TELEM2, que no existe en este firmware |
| `MAV_PROTO_VER` (→2) | Forzaría MAVLink v2 en el enlace del MTF-01P |
| `SYS_HAS_MAG` (→1) | **No hay magnetómetro conectado** (I2C bus 1 solo tiene 0x77 = baro SPL06) y el firmware no trae driver `qmc5883p`, solo `qmc5883l` |

Lo que sí entró: mapeo de motores (`PWM_MAIN_FUNC1..4` = 101/104/102/103), `PWM_MAIN_TIM0=-3`
(DShot600), geometría `CA_ROTOR*_P*` (±0.17), PIDs `MC_*RATE_*`, límites indoor `MPC_*`,
mapeo RC completo, batería 6S, y la config de flujo óptico (`EKF2_OF_CTRL=1`,
`EKF2_HGT_REF=2`, `EKF2_GPS_CTRL=0`, `EKF2_OF_QMIN=30`, `EKF2_RNG_A_HMAX=12`).

Los 97 se escribieron por MAVLink con verificación de lectura de vuelta (0 fallos) y
sobreviven al reinicio.

### Sensor MTF-01P (flujo óptico + lidar 12 m)

Conectado a **TEL4 / UART8 = `/dev/ttyS7`** (SH1.0-4P "GVRT", PE0=RX PE1=TX, **5V**,
115200, protocolo `Mavlink_PX4`). TEL4 no es un puerto declarado en la 1.14.3, así que
ningún `MAV_x_CONFIG` lo levanta. Se arranca desde el hook de la SD (`rcS` línea 486):

`/fs/microsd/etc/extras.txt`:
```
mavlink start -d /dev/ttyS7 -b 115200 -m minimal
```

Verificado: `rx ~7400 B/s`, msgid 106 + 132, `vehicle_optical_flow` quality ~90-97.
⚠️ `SENS_FLOW_ROT` no existe en este build → rotación fija en 0, el sensor debe ir
montado con su eje X hacia adelante.

## Cómo reconstruir / flashear una versión

**Reconstruir desde un diff guardado:**
```bash
cd /home/kmedrano/PX4-Autopilot
git checkout boards/hkust/nxt-dual/           # limpiar board
git apply <version>/board_config.diff         # aplicar la config de esa versión
make hkust_nxt-dual_default                    # compilar
```

**Flashear un .px4 ya compilado (sin recompilar):**
```bash
# QGC → Vehicle Setup → Firmware → Advanced → Custom firmware file → elegir el .px4
# o por línea de comandos con el uploader de PX4
```

**Recrear V0 (stock, sin ninguna mod):**
```bash
cd /home/kmedrano/PX4-Autopilot
git stash push boards/hkust/nxt-dual/          # guardar mods actuales
make hkust_nxt-dual_default                     # build stock
git stash pop                                    # recuperar mods
```

## ⚠️ El firmware NO se puede leer del FC

El bootloader del NxtPX4v2 es **rev 5**; los comandos de lectura de flash
(`CHIP_VERIFY` 0x24 / `READ_MULTI` 0x28) son *rev2-only* y los rechaza. Por eso
la regla 1 de abajo es crítica: **si no guardaste el `.px4` antes de flashear,
ese binario se pierde**. Únicas vías de recuperación: DFU por BOOT0
(`dfu-util -a 0 -s 0x08000000:1835008 -U dump.bin`, requiere RDP nivel 0),
sonda SWD, o pedírselo al fabricante.

## ⚠️ Reglas
1. **Antes de cada `make` que vaya a reflashear**, copiar el `.px4` de `build/` a una carpeta `vN_fecha_desc/` (el build sobrescribe).
2. **Antes de cada reflasheo**, backup de params (QGC → Save to file) — el flasheo **resetea params**.
3. Guardar siempre el `board_config.diff` + `base_commit.txt` con cada binario.
