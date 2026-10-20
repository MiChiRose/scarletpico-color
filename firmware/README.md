# ScarletPico Color firmware

**Latest RP2040 UI candidate (2026-10-20):**
[v2.2.7 UI POLISH](releases/2026-10-20-rp2040-ui-polish/README-RU.md).
Based on the user's working 2.2.6, preserving its LCD/game/audio/clock/battery
bytes. Cleaner bilingual library, focus-only updates, shorter boot and 12ms
UI debounce. ARM tests reduce adjacent-selection pixel traffic by 92.53%;
this is not a physical FPS/latency claim. Exact 2.2.6 rollback is preserved.

**Previous RP2040 battery build — preserved working 2.2.2 base (2026-10-20):**
[v2.2.6 LEGACY222 GP29](releases/2026-10-20-rp2040-legacy222-battery/README-RU.md).
User confirmed the exact 2.2.2 rollback works with the same soldered divider,
whereas both native 2.2.5 variants do not. This append-only battery extension
preserves the old LCD initialization/transport, core, clocks and 356x320 game.
New firmware still needs physical acceptance; the base has been accepted.

**Historical native RP2040 divider test (2026-10-20; superseded):**
[v2.2.5 GP29-only battery + voltage](releases/2026-10-20-rp2040-gp29/README-RU.md).
**Device report: menu unreadable; NOT hardware-accepted.** Separate
[LCD12 diagnostic build](releases/2026-10-20-rp2040-gp29-lcd12-check/README-RU.md)
reduces only the LCD SPI request to 12.5 MHz; root cause is not confirmed.
Battery icon at top right, voltage below, both menu and game. Enabled by
default for the confirmed two 472 (4.7 kΩ) resistor divider. No charger-status
GPIOs, no inferred charging state. Exact prior releases below are preserved.
Computer tests do not replace checking the actual ADC and wiring.

**Optional battery-monitor test for RP2040 (2026-10-20):**
[v2.2.4 battery + TP4056 status](releases/2026-10-20-rp2040-battery/README-RU.md).
Adds voltage bands, charger state and a low warning in menu/game. OFF by
default; requires a power-off-safe ADC divider and two isolated status inputs.
Software and compiled ARM tests passed; actual wiring/ADC is not verified.
The existing 2.2.3 release below remains unchanged for rollback.

**Previous baseline for the verified connected RP2040 (2026-10-07):**
[v2.2.3 native port + our menu](releases/2026-10-07-rp2040-native-menu/README-RU.md).
This is a complete Cortex-M0+ rebuild, not an RP2350 UF2 family-ID patch or a
replacement of the factory USB bootloader. Native GB/GBC core and LCD transfer
functions are preserved; RAM layout and sound DMA IRQ are adapted for RP2040.
Important limitations: standard ROM up to 1 MiB, cartridge RAM up to 32 KiB,
new save paths/state format. Exact previous 2.2.2 rollback and source ZIP are
beside the UF2. Computer tests passed; no automatic flashing or physical FPS test.

**Latest RP2350-Zero test (2026-10-07):**
[v3.0 native + our menu](releases/2026-10-07-rp2350-native-menu/README-RU.md).
This is a source rebuild of the supplied native RP2350 project, not a patch
to an RP2040 binary. It preserves the supplied core/header and native video
function bodies, uses profile B (CPU 200 MHz, LCD request 100 MHz, x2 320×288),
and adds our existing launcher, boot/chime, pause/settings and five-slot
snapshots with I2S audio. The new UF2, unchanged native B rollback and portable
source ZIP are in `releases/2026-10-07-rp2350-native-menu/`.
Tests run on the computer, not on the physical console; no automatic flash.
See the release notes for differences in ROM limits, save paths and CPU settings.
This RP2350 build is not compatible with the connected board: factory ROM read
identified that chip as RP2040 despite the expected RP2350 model.

## RP2040 history

**Latest performance test (2026-09-28):** [SHADOW FAST](SHADOW-FAST-TEST.md)
specializes the exact previous-frame cache codec: aligned pair comparisons,
packed-row writes and no repeated tile-coordinate division. The same pixels
and regions require fewer ARM codec instructions in differential tests; this
is not a measured physical FPS gain. No new RAM, clocks, core/APU, DMA or UI
changes. New UF2 and exact Pause Settings rollback:
`releases/2026-09-28-shadow-fast-test/`. Never automatically flashed.

**Latest UI test (2026-09-28):** [In-game settings + bottom FPS](PAUSE-SETTINGS-TEST.md)
adds Settings to the five-row Start+Select pause menu without unloading the game.
The actual LCD counter is now one line at the bottom of the left black rail.
Native 160×144 -> 356×320 nearest-neighbour scaling, sound, clocks, core and
[PACED scheduling](VIDEO-PACE-TEST.md) are unchanged. The exact PACED rollback
and the new UF2 are in `releases/2026-09-28-pause-settings-test/`.
No automatic flashing; physical acceptance is still required.

**Current experimental release (2026-09-28):** [Features v2.2.2](FEATURES-V2_2_2.md)
extends only the boot-chime tail; [Features v2.2](FEATURES-V2_2.md) added a compact
boot logo/chime to [Features v2.1](FEATURES-V2_1.md),
which adds About device and LCD-only FPS to [Features v2](FEATURES-V2.md).
Five snapshot slots, pause, 125/170/200 MHz profiles, paged ROM loading,
sound and the core are preserved. The v2.2 UF2 is retained for rollback.
See that document for the correct reproducible build and rollback instructions.
The older notes below describe earlier source-tree builds, not this binary base.

Earlier separate experiment: [compact lossless dirty-frame cache](VIDEO-SHADOW-TEST.md).
It preserves full-height 356×320 upscaling, CPU/SPI clocks and the emulation core.
Its [VIDEO16 base](VIDEO16-TEST.md) measured 23 LCD FPS on the console,
versus the earlier 18–19. Subsequent SHADOW/PACED observations and limitations
are recorded in [VIDEO-PACE-TEST.md](VIDEO-PACE-TEST.md). That test and its exact
23-FPS rollback are in `releases/2026-09-28-video-shadow-test/`.

## Historical source-tree build notes

First hardware test build for:

- Waveshare RP2040-Zero;
- ST7796 480×320 SPI display;
- SPI microSD module;
- eight active-low buttons;
- no audio.

The firmware starts with a vertical game menu, scanning `/roms` for `.gb` and
`.gbc` files, including long filenames. GB and GBC emulation use the pinned
Peanut-GB CGB branch with `PEANUT_FULL_GBC_SUPPORT=1`. No game auto-starts.

The selected ROM is cached in onboard flash, starting after the first 512 KiB
reserved for firmware. A full 1 MiB ROM fits; 2 MiB ROMs do not fit on this
2 MiB-flash board. Cartridge RAM saves are stored separately under `/saves`.
The known Zelda ROM keeps the legacy `/saves/zelda.sav` path.

Current releases:

- `releases/scarletpico-rp2040-pacman-fix-v0.9-125mhz.uf2`: current test build;
  separate small-region updates, APU read-mask fix, LCD-off loading fix.
  Full-height image, 125 MHz CPU and LCD SPI settings stay unchanged.
  See `PACMAN-FIX-V09.md`; real-board verification is pending.
- `releases/scarletpico-rp2040-full-height-v0.8-125mhz.uf2`: previous full-height
  build. The user reported poor Pac-Man LCD FPS and crashes; retained for history.
- `releases/scarletpico-rp2040-full-height-v0.8-oc250mhz.uf2`: the same changes
  with the previous 250 MHz / 1.20 V overclock. Experimental comparison only.
- `releases/scarletpico-rp2040-gb-gbc-menu-v0.7.uf2`: selectable game image size,
  second-core video output. Retained for history; the user reported full freezes.
- `releases/scarletpico-rp2040-gb-gbc-menu-v0.6.uf2`: GB/GBC menu, color output,
  per-game saves, safe LCD timing. Retained as the user's working rollback build.
- `releases/scarletpico-rp2040-sd-diagnostic-v0.5.uf2`: read-only filesystem test,
  including root directory listings before and after LCD initialization.

Version 0.9 always scales the native 160×144 frame to 356×320, without cropping,
and centers it on the 480×320 panel. Small integer-pixel rounding is unavoidable.
Black sidebars are 62 pixels each; the diagnostic FPS labels are in the left
sidebar, not over the game. There is no size selection in the menu anymore.
Unchanged frames send no image pixels. v0.9 sends separate tight changed regions,
instead of the single bounding rectangle in v0.8. Full-screen motion still has
the SPI bandwidth cost of a full image. See `PACMAN-FIX-V09.md` for the current
tests and `FULL-HEIGHT-V08.md` for the historical freeze investigation.

Earlier version 0.7 reduced the default game image to native 160×144, sending four
times fewer pixel bytes than v0.6. Left/Right in the menu selects FAST 160×144,
BALANCED 240×216 or LARGE 320×288. Core 1 sends the completed frame while core 0
runs game logic and prepares the next image, omitting pixel generation only
when both framebuffers are occupied. The
overlay reports LCD FPS and emulated FPS separately. No fixed hardware frame
rate is promised; see `PERFORMANCE-V07.md` for changes, tests and acceptance.

Version 0.6 replaces the fixed Zelda launch with a selectable game library,
adds the color-capable core, and reduces the LCD SPI request to 12.5 MHz.
The supplied Aladdin (CGB-only) and Zelda (DMG) ROMs each passed 1800 emulated
frames and reload tests on the host with AddressSanitizer/UBSan. Aladdin
reached its gameplay screen in color. This does not establish hardware speed
or fix verification on the user's physical wiring. The user subsequently
confirmed v0.6 works on the prototype, but reported about 4–10 FPS and Aladdin
stuttering. See `GB-GBC-V06.md` for the earlier implementation report.

Version 0.5 explicitly mounts the first MBR partition. The v0.4 hardware report
showed FAT16 at LBA 0, while macOS identified the intended FAT32 partition at
LBA 16. A synthetic regression test reproduces this mismatch and verifies the
partition-selection fix, including ROM reads and save writes. The later v0.6
game build retains this fix and worked in the user's hardware test.
See `PARTITION-FIX.md`.

Version 0.3 fixes an incompatibility in the bundled SD driver: v0.1 and
diagnostic v0.2 rejected standard-capacity (SDSC) cards, including the intended
2 GB card. `CARD INIT FAIL STATUS 01` only means initialization did not finish;
it does not prove a wiring fault or that the card never replied. Reformatting
cannot fix that driver limitation. See `SDSC-FIX.md` for the changes and tests.

## microSD layout

Use one MBR partition formatted FAT16 or FAT32. The firmware reads the first
partition's start from the MBR; it does not require a particular starting LBA.
Unpartitioned whole-disk FAT volumes are not supported by the v0.5 mapping.
The inspected `SCARLETPICO` card already has the required layout; do not
reformat it for this update.

Place any supported `.gb` and `.gbc` ROMs inside `/roms`; renaming them is not
required. The menu shows up to 32 files, sorted by filename, in seven-row
pages. macOS hidden/resource-fork files are ignored. A short `zelda.gb` copy
and the original long-named ROM may both appear; neither file is deleted.
Identical ROM header/size identities share the same save path.

The firmware creates `/saves` when necessary. Safely eject the card from macOS
before inserting it in the console.

## Controls

- Up/Down: select a game; held directions repeat.
- Select: select the next game.
- Game size is always FIT HEIGHT 356×320. Left/Right no longer changes size.
- A or Start: launch the selected game.
- B in the menu: rescan the game list.
- Hold Start+Select for 1.5 seconds in a game: save cartridge RAM and return
  to the menu. Both buttons are suppressed from the emulated game while the
  chord is held. The menu then requires a two-second cooldown and release of
  all buttons, so the held chord cannot restart the game.
- Hold B at power-on: keep a display test pattern visible until B is released.
  All four panel corners and the centered 356×320 game area should be visible.

Game inputs otherwise pass through unchanged. There is no audio in this build.

## Build on macOS

The easiest supported setup is Visual Studio Code plus the official
`Raspberry Pi Pico` extension. It installs the SDK and ARM toolchain. For a
command-line build, install CMake, Ninja and an Arm GNU `arm-none-eabi`
toolchain, then run:

```sh
cd firmware
cmake -S . -B build -G Ninja \
  -DPICO_BOARD=pico \
  -DPICO_TOOLCHAIN_PATH=/path/to/arm-gnu-toolchain
cmake --build build
```

The resulting file is `firmware/build/scarletpico.uf2`.

The default CPU clock is 125 MHz. `-DSCARLET_GAME_CLOCK_KHZ=250000` selects
the experimental overclock image; set it back to `125000` to restore stock.
The game menu and UF2 metadata identify the selected CPU clock.

The same build also produces `firmware/build/scarletpico_diag.uf2`, a
read-only hardware diagnostic image. The diagnostic uses a deliberately slow
1 MHz SD SPI clock and checks card initialization, FAT mount, the root
directory, `0:/roms`, `0:/roms/zelda.gb`, and the full ROM/header checksum.

## Flash over USB

1. Disconnect console battery/external power; use USB only for this test.
2. Hold the RP2040-Zero `BOOT` button.
3. While holding it, connect the USB-C data cable to the MacBook Air.
4. Release `BOOT`. A drive named `RPI-RP2` appears in Finder.
5. Copy `scarletpico.uf2` onto `RPI-RP2`.
6. The drive ejects automatically and the board reboots.

For a diagnostic test, disconnect USB and all other power for five seconds after
flashing, then reconnect normally with the card inserted. SD initializes before
the display, so a short blank screen during startup is expected. Allow up to
15 seconds for the diagnostic's full ROM read. No wiring changes are required.

No device driver is required. A charge-only USB cable will not work.

## Screen diagnostics

For an SD problem, flash the standalone release
`firmware/releases/scarletpico-rp2040-sd-diagnostic-v0.5.uf2`. It leaves the
FatFs result codes on the display, comparing directory and file lookups before
and after LCD initialization. Press A or Select to cycle through the summary,
the root listing before LCD initialization, and the root listing after it.
Listings store the first eight names and count up to 128 entries, with a
`COMPLETE` flag showing whether the directory end was reached. The full report
repeats every three seconds over USB serial. The test never writes to the card.
It shows the detected card type and, on initialization failure, the protocol
stage, last command and its raw R1 response. It checks the ROM header checksum
and reads the entire file, reporting its CRC32. For the user's Zelda
Rev.02 image (524288 bytes), the expected CRC32 is `34D08E7B`.

Expected final line:

```text
RESULT SD AND ROM READ OK
```

For the inspected card, the mount line should be `MOUNT CODE 0 FS 3 LBA 16`.
`FS 3` means FAT32; `FS 2` means FAT16. A different correctly formatted card
can legitimately have a different filesystem type or partition start.

Both current builds use SD SPI at 1 MHz after the 400 kHz initialization. The
v0.9 game and diagnostic request LCD SPI at 12.5 MHz. With the SDK switching
`clk_peri` to 48 MHz after a CPU clock change, the actual game LCD clock is
12 MHz. The USB log reports the actual value. Forced display color inversion
is off (`LCD_INVERT_COLORS=0`),
based on the inverted background/text observed in the user's v0.2 photo.
v0.6 worked on the user's panel; v0.9 performance/stability requires hardware verification.

The normal firmware shows readable error screens with a B-to-menu action.
`LOADING GAME` remains visible while the selected ROM is copied into flash.
Do not unplug during this operation. Switching ROMs replaces only the ROM
cache, not the firmware or SD ROM files.

At 12 MHz, a full 356×320 RGB565 pixel payload takes 151.89 ms, limiting full
image transfers to less than about 6.6 per second before overhead. Changed-region
updates can be faster when only part of the image changes; scrolling the whole
scene may need the full payload. Software upscaling is not free SPI bandwidth.
Core 1 transfers immutable completed frames using two buffers; core 0 continues
game logic. An optional third native-size buffer records the last displayed
image for exact comparisons; if it does not fit, full redraws remain available.
SD saves wait for the LCD to release SPI, and core 1 stops before flash caching
or clock changes. LCD FPS counts image updates, excluding identical-frame skips;
zero LCD FPS on a static screen is normal if EMU continues to advance.

The 125 MHz release trades CPU speed for a stock-clock stability test. If the
emulator or video path stalls, an eight-second watchdog can reboot into a
`RECOVERED FROM FREEZE` report (a video stall is recognized after two seconds,
so total delay can be about ten seconds). Photograph that screen, then press A.
Last PC is a breadcrumb, not a complete crash dump or a proven fault address.
Unsaved game progress can be lost. The watchdog is disabled during SD writes
and ROM flash caching to avoid forcibly interrupting these operations. It does
not cover all possible SD/power/hardware failures and is not a root-cause fix.

### Card inspection on 2026-09-26

macOS confirmed one MBR partition, FAT32, volume `SCARLETPICO`, starting at
LBA 16 with 4096-byte clusters. Both `/roms` and `/saves` already existed at
the root. The v0.3 `ROMS DIR FR_NO_PATH CODE 5` cannot be explained by a
missing folder on the inspected card.

Zelda had its original long filename and matched the project's ROM SHA-256
`ed42628d5cd8c73a6f8c6a8965f19674876a4fa04e616834e26b81b35963ad87`.
A copy named `/roms/zelda.gb` was added for the current fixed-path game build.
The original Zelda and Aladdin files were preserved. A missing `zelda.gb`
explains a later file-open failure, not the earlier `/roms` lookup error.
The subsequent v0.4 photo shows `FS 2 LBA 0`, an empty root both before and
after LCD initialization, `ROMS CODE 4`, and `ZELDA CODE 5`. The firmware is
therefore not opening the same volume as macOS. Version 0.5 addresses this
by selecting MBR partition 1 instead of accepting whole-disk FAT detection.
The stale-boot-record mechanism is reproduced with synthetic sectors; the
actual card's raw sector contents were not captured.

If the picture is upside down, change `LCD_MADCTL_VALUE` in
`include/config.h` from `0x28` to `0xE8` and rebuild.

## Saves

Game cartridge RAM is written every ten seconds after changes and when
returning to the menu. Save failures retain dirty RAM and allow retry before
leaving a game. Wait for the menu before switching power off. Saves are
cartridge RAM, not full emulator save-states: use the game's own save function.
Aladdin's ROM declares no cartridge RAM, so it has no `.sav` progress file.
Power loss during a card write is not guaranteed safe; writes are not yet
transactional. RTC persistence and sound are not implemented in this build.

## Licensing

Emulation uses the Peanut-GB CGB branch under its MIT license; provenance is
recorded in `vendor/Peanut-GB-CGB-PROVENANCE.md`. SD access uses pico-fatfs-sd
under Apache-2.0 with FatFs under its permissive license. The Pico SDK is
BSD-3-Clause.
