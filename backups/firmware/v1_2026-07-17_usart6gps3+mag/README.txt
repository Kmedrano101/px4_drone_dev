VERSION V1 — la que está flasheada actualmente en el FC (2026-07-17)
====================================================================
Base: PX4 commit 82e3322e (1.17.0 main)
Mods (sin commitear, en board_config.diff):
  - USART6 sin consola serie + GPS3->ttyS5  (INÚTIL: debug es SWD-only)
  - Drivers mag QMC5883P/L, IST8310, HMC5883 + qmc5883p auto-start (brújula)
Consola del sistema: solo por USB (ttyACM0)
FLASH: 98.54%
Params correspondientes: backups/backup_fc_2026-07-23.params
Para reflashear esta versión:
  make hkust_nxt-dual_default upload   (tras aplicar board_config.diff)
  o flashear directamente el .px4 con QGC
