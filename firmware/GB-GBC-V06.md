# v0.6: game library, GB/GBC core and display stability

## Hardware remains unchanged

RP2040-Zero with 2 MiB flash, ST7796 480x320 SPI display, shared-SPI microSD,
and the eight existing GPIO buttons. No rewiring, card formatting, driver
installation, BIOS download or ROM renaming is needed for this update.

## Display finding

The v0.5 game build requested 62.5 MHz for LCD initialization while the
readable diagnostic used 12.5 MHz. After switching CPU clocks, the default
Pico SDK peripheral clock becomes 48 MHz, so the old game transfer rate was
24 MHz, not a constant 62.5 MHz. Both exceed the conservative limit inferred
from the ST7796S's 66 ns minimum SPI write-cycle specification (about 15 MHz).
See [manufacturer datasheet, section 7.4.3, page 54](https://files.waveshare.com/wiki/common/ST7796S_Datasheet.pdf).

v0.6 requests 12.5 MHz from initialization onwards (12 MHz after the clock
change), keeps commands and their parameters in one CS transaction, and adds
explicit CS/DC setup and hold margins. Landscape remains `MADCTL=0x28`, with
RGB565 `COLMOD=0x55`. This is a plausible correction for corrupted orientation
or address commands; the photo alone does not prove electrical corruption.

The production driver is tested with a simulated command decoder: all 92,160
game pixels reach the expected centered 320x288 region, including coordinates
above 255 and the bottom/right edges, with correct 2x scaling and byte order.
The test also rejects simultaneous SD/LCD selection and excessive SPI requests.
It cannot validate the physical wire signals.

## GB/GBC support

The previous DMG-only core could not run Aladdin: byte 0x143 of the supplied
ROM is 0xC0 (color required). The CGB branch now supplies banked VRAM/WRAM,
color palettes and CGB CPU behavior. Color is resolved per scanline, rather
than reducing every pixel to the old four-shade palette.

The old cache also left only 1 MiB minus 4 KiB for ROM data. The new cache
starts at 512 KiB, followed by a 4 KiB metadata sector, so the entire 1 MiB
Aladdin ROM fits. A runtime boundary check prevents the cache from erasing
firmware. ROMs of 2 MiB or larger still cannot fit this board's flash layout.

The green menu scans real filenames in `0:/roms`, filters directories and
macOS junk, sorts games, and shows seven rows per page, up to 32 entries.
Selection uses Up/Down or Select; A/Start launches. Start+Select held for
1.5 seconds saves and returns to the menu. A full button release and two-second
cooldown prevent the old held-button relaunch problem.

Cartridge RAM is allocated according to the ROM header. Insufficient memory
is reported rather than overwritten. Distinct header/size identities get
separate save names; the known Zelda Rev.02 header retains `zelda.sav`.
These are battery-RAM saves, not instant save-states. Aladdin has no cartridge
save RAM. RTC persistence, transactional save replacement and audio remain
outside this build.

## Verification

- `test_emulator_roms.c`: the exact supplied Aladdin and Zelda each ran 1800
  frames plus a fresh 120-frame reload through the production wrapper, with
  AddressSanitizer and UBSan enabled. No errors were reported. Captured Aladdin
  frame 1800 shows the playable level/pause screen in color; Zelda is DMG.
- `test_game_library.c`: both real long-named files are ready, GB/GBC mode is
  correct, sort/filter/limits work, saves are separated and legacy Zelda is
  mapped correctly. This uses a read-only host adapter for the FatFs API.
- `test_launcher.c`: production menu code with simulated time/GPIO/storage;
  no boot autostart, Down then Start selects the second ROM, and transition
  cooldown waits for held buttons to be released.
- `test_display.c`: actual production display driver with simulated SPI/GPIO.
- Existing SDSC and MBR partition regression tests remain applicable.
- RP2040 UF2 compiled and memory layout checked; no physical-board success
  is claimed until the user tests the artifact.

Host tests use clang from `/Library/Developer/CommandLineTools/usr/bin/clang`
and sysroot `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk`. Use
`tests/run_host_tests.sh` from the project root to repeat the checks. Real
ROM smoke tests run only when the two supplied ROM files exist locally.

## Hardware acceptance

1. Flash `scarletpico-rp2040-gb-gbc-menu-v0.6.uf2` via BOOT / RPI-RP2.
2. Fully disconnect power for five seconds. Boot normally with the same SD.
3. Confirm a stable full-height game menu, not an automatic Zelda launch.
4. Select Aladdin; wait on LOADING GAME for flash caching, then confirm color.
5. Hold Start+Select, release both, wait for the menu cooldown; choose Zelda.
6. Check controls and Zelda's own in-game save, then return to the menu before
   turning off power.
7. If geometry is still wrong, hold B while powering on and keep it held to
   photograph the full-panel border, TL/TR/BL/BR labels and central test area.

The slow LCD setting bounds full-frame refresh below about 8 FPS before other
overheads. Emulated frames can catch up between transfers, but smooth video,
real-time GBC speed and low input latency are not guaranteed in this build.
