# ScarletPico Color 3.0 — native RP2350 + our UI

This folder started as the supplied `scarletpico-rp2350-for-agent.zip`.
The original README/HANDOFF/manifest describe **test1 before this merge**.
This file and the release README describe the merged application.

## What comes from each project

- Supplied RP2350 base: unmodified Peanut-GB GB/GBC header, RAM execution,
  scanline conversion, three-buffer ownership, core-1 worker, ST7796 driver,
  SPI/DMA row pipeline, x2 320×288 image, shared SD/LCD bus, flash ROM cache.
- Our project: `firmware/ui-addon/ui.c` skin/dirty regions/spinner/card error,
  `firmware/features-addon/boot.c` logo/chime, `pause.c` and five-slot menus,
  existing minigb APU and I2S program. Native SDK bindings replace old addresses.
- New integration: `console_ui.c`, `console_audio.c`, `console_state.c`.
  Front-end ROM table bounds checks, safe save-size lookup and non-returning
  fatal-error escape are added without editing the core header.
- Audio claims separate DMA channels, PIO1 and DMA IRQ2. Debug USB output is
  non-blocking to avoid a default 500 ms stall when a host stops reading.
- Our first-partition mapping fix is retained in FatFs configuration and
  `partition_map.c`: this card previously contained stale FAT16 metadata at
  sector 0 hiding its real FAT32 partition. No hard-coded sector offset.

Profile B is retained: CPU/peripheral 200 MHz, LCD SPI request 100 MHz,
SD request 12 MHz. No new 240/250 MHz clock profile is enabled. This release
shows CPU frequency read-only; volume and brightness work both from library
and pause. Runtime clock switching is deliberately not ported in this test.

## Build

Pico SDK 2.3.1 (including tinyusb), ARM GCC 14.3.1, picotool 2.3.0, CMake,
Ninja and Python 3 were used. Source dependencies retain their licenses.
The SDK/toolchain are not included in the portable source ZIP.

From the directory containing `firmware`:

```sh
python3 firmware/tools/build_rp2350_native.py \
  --sdk /path/to/pico-sdk --toolchain /path/to/arm-gnu \
  --picotool /path/to/picotool --pioasm-dir /path/to/pioasm/cmake/package
```

Optional `--incoming-source /path/to/original.zip` asserts that the kernel
header and the listed native video functions are unchanged. Optional
`--rollback /path/to/native-B.uf2` adds a SHA-pinned original B copy.
Output: `firmware/releases/2026-10-07-rp2350-native-menu/`.
This script **never loads firmware onto a device**.

Alternatively use the supplied `build.sh B`, setting `PICO_SDK_PATH` and
`PICO_TOOLCHAIN_PATH`; use `-DSCARLET_PICOTOOL=...` if needed. The
`SCARLET_RETARGET_COMPAT` option is OFF with standard ARM GCC, ON only for a
toolchain that actually needs the original Arduino malloc compatibility shim.

## Tests and limits

`bash firmware/tests/run_rp2350_tests.sh /path/to/game.gb /path/to/game.gbc`
uses macOS clang ASan/UBSan plus Python `unicorn`, `capstone`, `pyelftools`.
Unicorn needs local JIT permission; it does not access USB hardware.

Host testing is not physical FPS, SD timing, panel stability or audible quality.
CPU 200 MHz exceeds RP2350's rated 150 MHz; 100 MHz SPI is experimental.
No physical tests have been run on the console for this merged image.

ROMs use `0:/roms` (with folder browsing/root fallback), a first MBR partition
formatted FAT16/FAT32. An unpartitioned superfloppy is not used by this build.
Native flash caching allows at most 3.5 MiB, i.e. normal ROM sizes up to 2 MiB.
4/8 MiB streaming from the old RP2040 addon is not included.
Native `.sav/.rtc` paths are unchanged: `/scarlet2350/saves/<filename>.sav`.
Snapshots are separate `/scarlet2350/states/<whole-ROM-CRC>-<slot>a/b.sps`.
No old files are deleted or automatically migrated. Old RP2040 snapshot
formats are incompatible. Games using 128 KiB cartridge RAM run, but snapshots
for them exceed the reused 138240-byte staging buffers and report no memory.
Snapshots with up to 64 KiB RAM fit. There are five slots, not one slot per
in-game account: each snapshot captures the whole cartridge/game state.
