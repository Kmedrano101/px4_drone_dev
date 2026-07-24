VERSION V2 — optimizada (2026-07-23)
=====================================
Base: PX4 commit 82e3322e (1.17.0 main)
Cambios vs V1:
  - REVERTIDO USART6/GPS3 -> consola serie RECUPERADA en USART6
  - QUITADO Grupo A: FW_* (5 modulos), VTOL_ATT_CONTROL, DIFFERENTIAL_PRESSURE
  - QUITADO Grupo B: mag IST8310/HMC5883, BATT_SMBUS, EXAMPLES_FAKE_GPS
  - CONSERVADO: brujula QMC5883P/L + qmc5883p auto-start, todos los esenciales MC/EKF2/DDS/LiDAR
FLASH: 92.01% (antes 98.54%) -> liberados ~117 KB
Consola: serie (USART6) + USB (ttyACM0)
Params: restaurar desde backups/backup_fc_2026-07-23.params tras flashear
