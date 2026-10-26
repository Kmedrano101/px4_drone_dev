VERSION V3 — limpia / optimizada multirotor (2026-10-26)
========================================================
Base: PX4 commit 82e3322e (1.17.0 main) — mismo que V1/V2.
Target: hkust_nxt-dual_default (board id 1013).

Objetivo: build mínima para lo que el FC#2 realmente usa, dejando sitio de
flash y habilitando el compás QMC5883P (ya presente en el board default).

FLASH: 83.06% (1 524 216 B / 1 792 KB)  -> V2 era 92.01%, V1 98.54%
RAM (AXI_SRAM): 11.77%

Cambios vs V2 (ver board_config.diff para el delta completo vs upstream):
  QUITADO:
    - Cámaras: CAMERA_CAPTURE, CAMERA_TRIGGER, MODULES_CAMERA_FEEDBACK
    - GIMBAL
    - IRLOCK + LANDING_TARGET_ESTIMATOR (sin baliza de aterrizaje)
    - OSD_MSP_OSD (sin OSD analógico; se usa DDS/QGC)
    - Estimador LPE viejo: ATTITUDE_ESTIMATOR_Q + LOCAL_POSITION_ESTIMATOR
      (redundante con EKF2) -> el mayor ahorro de flash
    - COMMON_DISTANCE_SENSOR (el MTF-01P entra por MAVLink, no necesita
      driver nativo)
    - COMMON_TELEMETRY (FrSky/HoTT/BST; NO es MAVLink -> no afecta al enlace)
    - SD_BENCH, SD_STRESS (solo benchmarking)
    - Baro: COMMON_BAROMETERS -> solo DRIVERS_BAROMETER_GOERTEK_SPL06
    - Mag: solo QMC5883P (quitado QMC5883L; el chip físico es el P @0x2C)
  CONSERVADO:
    - Todo MC + EKF2 + Control Allocator + Navigator (RTL/Land)
    - DShot, GPS (F9P), BMI088 x2, SPL06, QMC5883P (auto-start en rc.board_sensors)
    - RC_INPUT, PWM_OUT, buzzer, LED
    - MAVLINK (radio SiK + USB) y UXRCE_DDS_CLIENT (companion) -> telemetría intacta
    - Logger, Gyro FFT (notch dinámico), MC Autotune
    - Utilidades de diagnóstico: i2cdetect, perf, top, listener, dmesg,
      hardfault_log, nshterm, param, reboot, uorb, work_queue, mtd, gpio...

Para flashear:
  QGC -> Vehicle Setup -> Firmware -> Advanced -> Custom firmware file:
     hkust_nxt-dual_default.px4
  (o dfu-util; ver INDEX.md). El flasheo RESETEA params -> antes:
   - backup de params del estado actual (hecho: backup_fc_2026-10-26_pre-1.17.params)
   - tras flashear: restaurar params 1.17 + recalibrar (CAL_* se borran).
