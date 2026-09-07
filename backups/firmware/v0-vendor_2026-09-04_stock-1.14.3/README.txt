VERSION V0-VENDOR — firmware de fabrica que estaba en el FC (2026-09-04)
=========================================================================
Esto es lo que el FC tenia flasheado al iniciar la sesion del 2026-09-04:

  PX4 1.14.3  |  branch micoair743-v1.14.3  |  git 4a0e65f2  |  build Nov 19 2024

NO es V1 ni V2 de este indice (esas son 1.17.0 sobre el commit 82e3322e).
El FC fue reflasheado con el firmware del fabricante en algun momento
posterior al 2026-07-23.

## ⚠️ No hay binario en esta carpeta — y no se puede obtener del FC

El bootloader del NxtPX4v2 es **rev 5**. Los comandos de lectura de flash
(CHIP_VERIFY 0x24 y READ_MULTI 0x28) son **rev2-only** y este bootloader los
rechaza. No existe ningun comando del protocolo PX4 para volcar la flash.

Vias alternativas para obtener el binario, si algun dia hace falta:
  a) DFU del sistema STM32: mantener BOOT0/boton BOOT pulsado al conectar USB,
     luego  `dfu-util -a 0 -s 0x08000000:1835008 -U flash_dump.bin`
     (solo funciona si RDP = nivel 0; da la flash COMPLETA, incl. bootloader).
  b) Sonda SWD (ST-Link / J-Link) sobre el header de debug.
  c) Pedir el .px4 original al fabricante (HKUST / Matek), rama micoair743-v1.14.3.
     El git-hash 4a0e65f2 NO existe en el repo upstream PX4/PX4-Autopilot.

## Lo que SI quedo respaldado

  ver_all.txt          - identidad exacta del firmware que corria
  bootloader_info.txt  - rev del BL, board id, tamano de flash, IDs USB
  ../../backup_fc_2026-09-04.params  - 909 parametros leidos por MAVLink

Board id 1013 y flash 1835008 B confirman el target de build: hkust_nxt-dual.

## Pendiente
  - dataman (/fs/microsd/dataman, 62560 B — misiones/geofence): no descargado,
    QGroundControl tenia tomado /dev/ttyACM0 durante la sesion.
