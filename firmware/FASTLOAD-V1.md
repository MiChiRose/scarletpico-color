# ScarletPico Color — UI v1 Fastload

This is a loading-only experiment for the existing **RP2040-Zero / ST7796
480×320 / MAX98357A** console. It is not an RP2350 firmware.

Both ready-to-flash files are kept together in
[`releases/2026-09-28-rollback-and-fastload`](releases/2026-09-28-rollback-and-fastload/):

- `01-current-ui-v1-ROLLBACK.uf2`: exact, unchanged UI v1 release.
- `02-ui-v1-FASTLOAD.uf2`: the same release with the two loader optimizations below.

Flash **one** of these files using the usual BOOTSEL/UF2 procedure. To undo the
experiment, flash `01-current-ui-v1-ROLLBACK.uf2` the same way. No microSD changes,
new system directory, formatting, driver installation or save conversion are
required. Settings and ROM cache addresses are unchanged; neither UF2 includes
the settings sector or the game-cache sectors. The menu intentionally looks
identical, including its version text.

## Changes

1. The sequential ROM-data read call uses a temporary **4 KiB read-ahead buffer**.
   The original loader still writes exactly the same 256-byte flash pages and
   commits the same cache metadata, in the same order. Header reads and all
   save-file operations remain separate from read-ahead.
2. SPI is restored to the SD configuration after a loading-spinner draw, rather
   than being redundantly reconfigured after every 256-byte page. The spinner
   has the same drawing code, appearance and 100 ms update interval as UI v1.

The buffer is allocated lazily on the first data read, not for a warm cache hit.
It is freed before returning to the original game-launch path, on success and
every normal error return. If allocation fails, the old 256-byte read path is
used. No 4 KiB array is placed on the already limited MCU stack.

Only **16 bytes** of permanent bookkeeping RAM and **332 bytes** of appended
flash code are added. Three loading call sites and the BSS/heap/firmware-end
metadata change: **11 existing payload bytes** differ. Every other byte of UI v1
is identical, including the whole UI, emulator, game scaling and frame pacing,
audio/APU/mixer/I2S/DMA, input handling and CPU/LCD/SD frequency configuration.
The requested game CPU/LCD/SD settings remain 200 MHz / 50 MHz / 12.5 MHz.

This is **not** a large-ROM/paging implementation: `ROM TOO LARGE` and the existing
approximately 1.5 MiB ROM-cache limit remain. It is intended to reduce loading
overhead, not increase game FPS or alter compatibility.

## Verification

- Pinned input SHA-256; independent decoding of all three Thumb call patches.
- A whole-payload comparison rejects any changes outside six allowlisted
  loader-call/metadata locations. The rollback file is hash-checked and is never
  overwritten with the new build.
- ASan/UBSan native tests cover more than 540 file sizes and tails, allocation
  failure, cache hit, read errors, short reads, retry and the SPI/timer guard.
- Actual final ARM machine-code tests run the original storage writer with
  peripheral and FatFs I/O stubs. Tests check ROM sizes 32 KiB through 1 MiB,
  exact ROM bytes/flash page order/cache marker, buffer cleanup, error and
  allocation-failure paths, zero/oversize rejection and the real main-loop call.
- The 1 MiB case requests **256 × 4096-byte reads**, plus the unchanged header
  read; the old data path requests **4096 × 256-byte reads**. This is a 16×
  reduction in application-level data-read calls, **not a claim of 16× faster
  loading**. FatFs already buffers sectors; flash erase/program times remain.
- UI/audio ARM regression tests pass: settings, PWM limits, no-card retry,
  navigation, ABI/stack preservation, actual PCM gain and I2S behavior.
- Zelda GB and Aladdin GBC each pass a 120-frame actual-ARM smoke test with sound.
- Native UI dirty-region/visual tests pass. The UI machine code and assets were
  not rebuilt or modified for this release.

These are host/simulator tests. The microSD's real transfer latency, multi-sector
read behavior on the assembled wiring and physical-device loading time have not
been measured for this build. Nothing was automatically flashed to the console.

To compare on hardware, load one game and then a **different** game before each
measurement; immediately reopening the cached ROM does not measure SD loading.
Compare the same game pair with both builds. Check sound, buttons and return to
menu as usual. Do not unplug the device while it is loading/programming flash or
saving progress. If the new build is worse, return to the rollback UF2.

## Build

Do not rebuild the unrelated older `src/main.c` snapshot. Build the loader layer
against the exact pinned UI v1 UF2 and its verified UI ELF:

```sh
/Library/Developer/CommandLineTools/usr/bin/python3 firmware/tools/build_loader_addon.py
```

Sources: `loader-addon/`; binary changes and hashes: adjacent release JSON.
`tests/test_loader_native.c` links with the exact `loader-addon/loader.c` source.
`tests/test_loader_arm.py` requires the existing Unicorn/Capstone/pyelftools test
environment and also runs the UI/audio ARM regression suite.

## SHA-256

Rollback: `40063b38b3413c9fd7ed7c0aebe92ad59f0942546a2292b3efb527b626d8c9ee`

Fastload: `57bdbaaa2bedebf3797e103f4fa80e2ff975e481b9504b6bb276bbaa6c6f1964`
