# v0.9: Pac-Man compatibility and small-region display updates

## Scope and hardware status

The user reports about 6 LCD FPS and exits/crashes in Pac-Man on the 125 MHz
build. The exact physical crash screen and ROM variant have not been received.
No board is connected to this session. These changes fix reproduced software
defects; they do not establish that every reported physical crash is resolved.

Release: `releases/scarletpico-rp2040-pacman-fix-v0.9-125mhz.uf2`.
SHA-256: `492465708f48c0033fee4b9b5436388987a72fd48c06fb40e4573c1a779d27ea`.
RP2040 only, CPU 125 MHz, unchanged voltage, unchanged LCD SPI request
12.5 MHz (12 MHz after the SDK clock switch), unchanged SD SPI and wiring.
No new driver or library needs installing on the Mac. Audio stays disabled.

## Changes

1. **Distant moving objects no longer force one huge rectangle.** The old
   display driver enclosed all changed pixels in one bounding rectangle. The
   replacement records tight changed-pixel bounds inside 8x8 native tiles,
   merges nearby horizontal spans and vertically identical spans, and sends
   separate windows. A fully changed image still merges into one window.
   Mapping tables are cached; the SPI bus is selected once per image update,
   not per small region. No extra framebuffer or heap allocation is needed.
2. **Muted APU reads stay inside their table.** A core bug indexed a 48-byte
   table with `address - FF00` instead of `address - FF10`. That corrupted read
   values and read out of bounds at FF30..FF3F. The old failure was reproduced
   on Pokemon Yellow with sanitizers; all 48 registers now have regression tests.
3. **LCD-off loading is not a crash.** Pac-Man Special Color Edition previously
   stopped at frame 1 with `FRAME TIMEOUT PC 1614 LCD 43`. Games can legitimately
   leave their virtual LCD off during long initialization. The core now yields
   after 70224 base-clock ticks while LCD is off, with CGB double-speed handling,
   without advancing LY/STAT or generating a fake VBlank interrupt. This ports
   the approach from the non-CGB upstream core. The outer instruction guard and
   hardware watchdog remain; an inner HALT deadlock is still watchdog territory.

The image remains 356x320, with 62-pixel black sidebars. No crop, forced small
image, reduced color depth or increased hardware clocks were used for these gains.
Menu selection, GB/GBC support, save paths and Start+Select behavior are unchanged.

## Measured software checks

Production emulator and display code were run together on the Mac with
AddressSanitizer/UndefinedBehaviorSanitizer. The simulated ST7796 checks the
actual SPI command stream and compares **every output pixel on all 3600 frames**.
The first 720 frames are excluded from traffic totals to separate startup.
Input scripts start the game and apply direction/action buttons. The monochrome
game receives only one Start press: a second one pauses it and is not gameplay.
Captured images were inspected to confirm gameplay rather than a paused menu.

| Local ROM | Old rectangle SPI bytes | v0.9 SPI bytes | Reduction |
|---|---:|---:|---:|
| Pac-Man (U) (Namco Hometek) [!].gb | 100,412,290 | 21,712,404 | 78.4% |
| Pac-Man Special Color Edition (U) [C][!].gbc | 115,400,386 | 24,503,875 | 78.8% |

Counts include pixel data and window-command bytes. They **are not physical FPS
measurements**, do not include all CPU/setup delays, and are not a claim of a
4.6x hardware FPS increase. Full-scene changes still require 227,840 pixel bytes;
the 12 MHz SPI limit on those updates is unchanged.

Additional checks:

- Each supplied Zelda/Aladdin and each selected Pac-Man/Yellow/Red ROM receives
  21,720 emulated frame intervals with reload/render-skip consistency and
  deterministic action inputs. This is automated coverage, not a full playthrough.
- Display tests cover isolated pixels, opposite corners, full-frame merge,
  160 randomized multi-object frames across four scales, trails/sidebars, and
  memory-allocation fallback in the concurrent video worker.
- Synthetic long LCD-off initialization (>200,000 CPU instructions), LCD-off
  looping with host responsiveness, invalid opcodes, no fake VBlank and CGB timing.
- Existing SD partition/addressing, launcher, button cooldown, save exclusion,
  multicore ownership and watchdog regression checks.
- ARM release build fits below the reserved 512 KiB firmware boundary. Compiler
  stack-usage output is enabled for inspection; this is not a hardware stack test.
  Binary end: `0x1002d950`; BSS: 117,780 bytes. The display-diff function's
  reported local stack is 344 bytes; framebuffer ownership/allocation is unchanged.

## Installation and physical acceptance

1. Disconnect USB, hold BOOT, reconnect to the Mac, then release BOOT.
2. Copy the v0.9 UF2 to `RPI-RP2`. Wait for the drive to disappear/reboot.
3. Confirm the menu reads **V0.9 / 125MHZ**. Use the same SD card; do not format it.
4. Start the same Pac-Man ROM that showed the problem. Compare active movement,
   not the title screen or pause state. Check both LCD and EMU counters.
5. Try several starts, deaths/restarts and Start+Select returns. Save in games
   that support it and return to the launcher before unplugging power.
6. If it exits or freezes, photograph all text on the error/recovery screen;
   allow about ten seconds for watchdog recovery before disconnecting power.

Old release files are preserved. A real-board run is still required before
calling this version stable. No ROMs, SD files or saves were changed by this work.

Reproduce host tests with explicitly supplied local files:

```sh
bash firmware/tests/run_host_tests.sh '/path/to/Pac-Man.gb' '/path/to/Pac-Man.gbc'
```

Tests never download games; extra frame captures go to a newly created temporary
directory. See `vendor/Peanut-GB-CGB-PROVENANCE.md` for upstream/local boundaries.
