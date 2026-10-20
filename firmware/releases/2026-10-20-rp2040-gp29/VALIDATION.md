# Validation — 2.2.5 GP29, 2026-10-20

UF2 SHA-256: `dd4b003c5014082b2828f8454f094c75ecee98a56fdc634c5bd0b660d17affce`.
Target RP2040 Cortex-M0+, UF2 family `e48bff56`. No USB device was accessed.

Passed:

- `tests/test_battery_model.c`: ADC conversion, filtering, invalid input,
  delayed low warning and hysteresis (ASan/UBSan host build).
- `tests/test_ui.c` with `SCARLET_NATIVE_SOURCE=1`, `SCARLET_RP2040_NATIVE=1`:
  navigation/dirty regions, settings persistence and error states (ASan/UBSan).
- `tests/test_rp2350_menu_arm.py --rp2040 --elf build-rp2040-gp29/scarlet2040.elf --battery-adc`:
  actual compiled ARM code, menu, volume/brightness flash persistence,
  pause/resume/exit, snapshot ABI, sound scheduling and DMA separation,
  two-frame ownership, GB/GBC generated test ROM execution.
- GP29-specific ARM tests: default ON; BAT2 ON/OFF persistence, BAT1/corrupt
  record migration; unchanged first 16 settings bytes; 472+472 voltage
  conversion; 1 Hz sampling; invalid values; low warning/recovery; voltage at
  y=28 below icon; all indicator rectangles/text within the right black rail.
- Build audit: flash below reserved settings sector, RAM headroom 27,284 B;
  GB/GBC core header and LCD driver hashes equal the 2.2.3 baseline.
- Prior 2.2.4 UF2 hash still
  `73e81ac4b093ea09859d1ebe50f7afd1f4124886a6e7c68abea286c1f5dd07e0`.

`menu-preview.png` is output of the actual compiled ARM menu/text/icon drawing
with display I/O captured into a pixel buffer. The 3.80 V value is simulated
test input, NOT a reading of the user's battery.

No physical verification of ADC accuracy, wiring, LCD/FPS, SD or charging.
Hardware boundaries are mocked in ARM tests. No automatic flashing.

Rebuild using `tools/build_gp29_release.py` with `--toolchain`, `--pioasm-dir`
and (optionally) `--sdk`. Run tests against the resulting ELF; the host test
build needs an appropriate C compiler/SDK, ARM tests need Unicorn/pyelftools.
