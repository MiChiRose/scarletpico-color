# 2.2.6 LEGACY222 GP29 — validation, 2026-10-20

Final UF2 SHA-256:
`e8c6c99223e571fd450ec213446bff1e702ce57671c3b994cbff59e9cbc92209`.
Base 2.2.2 SHA-256:
`98b80f2827d626e697b83034d426b77e5fe028e1792f30edaec50a80ab963089`.
The user confirmed the BASE works with unchanged new battery wiring.
No physical acceptance of the new addition yet; no automatic USB access.

## Build invariants

- Source UF2 hash/family/block sequence checked before any output.
- Original LCD init/transport, CPU core/APU, SPI/CPU profile code, DMA,
  scaler, shadow codec and all remaining original bytes unchanged outside
  the explicit white list in `build-audit.json`.
- Four exact BL call replacements (header underline, idle input, PACED
  bridge, worker HUD), two BSS/heap boundary literals, firmware-end metadata,
  same-length About version string. 19 actual changed base bytes.
- Added 1047 bytes code, 32 bytes permanent RAM, no heap allocation or
  additional framebuffer. New RAM is cleared by the original startup and
  excluded from the original malloc region. Settings sector not overwritten.

## Executed final ARM image

`tests/test_legacy_battery_arm.py` passed on the final `patched.bin`:

- Real ADC register writes/read loop, not a stubbed sample function: only
  GP29, ADC and its own clock/reset; no LCD/SD/CPU/SPI register writes.
- One discarded + 16 averaged conversions; raw2358 gives 3800mV; 1 Hz,
  invalid 0/5V, bounded hardware timeout, recovery, filtering/low hysteresis.
- Actual original menu/header/font executed before/after patches. Every
  pixel outside the 80x44 indicator matches the working 2.2.2 baseline.
- Real original inline input bridge preserves registers/condition flags,
  idle paints nothing. Existing input function, not a C substitute, runs.
- Real original PACED bridge preserves keys/offered/due and its special
  R7 frame-ready bit ABI. Only the costly game call is mocked in this test.
- Actual patched worker HUD call executes the original FPS and stack-only
  text routines. Full-height x62…417 game pixels unchanged, right-rail
  voltage entirely within x418…479; stack stays in original core1 bank.
- Timer-low wrap preserves one-second sampling.

`tests/test_video_heap_arm.py` on the SAME new image also passed. The exact
original allocator and startup succeed with 0/8/32/64/80KB SRAM allocations,
retain original 16-colour/4-colour/null cache fallback, reject producer OOM
with 100KB, and repeatedly free/reallocate video without leaks.

Physical ADC/voltage accuracy, signal integrity, real FPS, and wiring are
not simulated by these tests. The hardware-register boundaries are models.
No commercial ROM is required for these tests or included in this bundle.

## Re-run

```sh
python firmware/tools/build_legacy_battery_release.py --arm-bin /path/to/arm-gcc/bin
python firmware/tests/test_legacy_battery_arm.py
SCARLET_HEAP_IMAGE=firmware/build-battery-legacy-addon/patched.bin python firmware/tests/test_video_heap_arm.py
```

The portable addition ZIP includes the first test and exact base UF2;
the pre-existing allocator regression is in the main workspace. No SDK is
needed to build the append-only addition. Unicorn/pyelftools are needed for
ARM tests; the older allocator test also uses Capstone.
