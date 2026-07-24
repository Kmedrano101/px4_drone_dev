# Índice de versiones de firmware — NxtPX4v2 (hkust_nxt-dual)

Base común: **PX4 commit `82e3322e`** (1.17.0 main). Todas las mods de board son **sin commitear**;
cada versión guarda su `board_config.diff` para reconstruirla exacta.

Repo de código: `/home/kmedrano/PX4-Autopilot`
Params correspondientes al estado actual: `../backup_fc_2026-07-23.params`

## Versiones

| Versión | Binario | Estado | Descripción |
|---|---|---|---|
| **V0** stock | ❌ recreable | referencia | Board sin mods (git limpio + build) |
| **Original+mag** | ❌ recreable | ~la que voló bien | Stock + drivers mag (sin USART6/GPS3) |
| **V1** | ✅ `v1_2026-07-17_usart6gps3+mag/` | **EN EL FC ahora** | + USART6 sin consola + GPS3 (inútil) + mag |
| **V2** | ⏳ pendiente | objetivo | Revert USART6/GPS3 + optimización (quitar FW/VTOL/etc.) |

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

## ⚠️ Reglas
1. **Antes de cada `make` que vaya a reflashear**, copiar el `.px4` de `build/` a una carpeta `vN_fecha_desc/` (el build sobrescribe).
2. **Antes de cada reflasheo**, backup de params (QGC → Save to file) — el flasheo **resetea params**.
3. Guardar siempre el `board_config.diff` + `base_commit.txt` con cada binario.
