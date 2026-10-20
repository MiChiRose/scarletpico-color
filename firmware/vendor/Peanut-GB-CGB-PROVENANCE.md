# Peanut-GB CGB core

- Upstream: https://github.com/deltabeard/Peanut-GB
- Branch: `cgb`
- Pinned commit: `33f053b9e70297ff0bab53da527c19126384d911`
- Local directory: `Peanut-GB-CGB`
- License: MIT, reproduced at the start of `peanut_gb.h`.
- Downloaded on 2026-09-26. Local changes for firmware v0.9 are listed below.

## Local fixes (2026-09-26)

- Muted APU register read-mask index starts at FF10, not FF00. Previously
  FF10..FF2F returned wrong mask values and FF30..FF3F read out of bounds.
  Reproduced with AddressSanitizer/UBSan on the user's local Pokemon Yellow.
- LCD-off CPU loops yield at 70224 base-clock ticks without fake VBlank/LY
  changes. This ports the non-CGB upstream core's `lcd_off_count` approach,
  accounting for CGB double speed. Pac-Man Special Color Edition previously
  hit the wrapper's instruction limit at frame 1, PC 1614, LCDC 43.
- Braces clarify the existing LCD-on double-speed timing; behavior is unchanged.

`tests/test_emulator_core.c` checks all 48 APU masks, a >200,000-instruction
LCD-off initialization, absence of fabricated VBlank, and double-speed timing.

`src/emulator.c` enables full CGB support, converts the core's RGB555 palette
to RGB565 per scanline, handles GB shades separately, checks header array
indices before initialization, and wraps unrecoverable errors with setjmp/
longjmp as required by the core callback contract. It calculates cartridge
RAM size locally because this branch's `gb_get_save_size` table lacks code 5.

This branch is preliminary and not an assurance that every GB/GBC title works.
The actual supplied Zelda and Aladdin images have host-side smoke tests;
physical RP2040 performance and input/display timing require hardware tests.

## Sound-only v0.9-B addon (2026-09-27)

The bundled MIT-licensed `examples/sdl2/minigb_apu` is used by the separate
binary addon, not by the default silent firmware target. Local APU changes:
16 kHz configurable sample rate; callback respects its byte length; deterministic
reset with NR52 powered before initialization; bounded register accesses; wave
RAM writes while powered off; correct disabling of DAC channels; envelope
underflow clamp; and noise length writes no longer overwrite the noise union.
This is a lightweight, frame-batched APU, not a cycle-accurate audio emulator.
Its original LICENSE remains beside the sources. See `firmware/AUDIO-V09-B.md`.
