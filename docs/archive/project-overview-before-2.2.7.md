# ScarletPico Color — историческое описание до 2.2.7

Исторический снимок прежнего README. Актуальные инструкции — в корневом README.md; относительные ссылки ниже относятся к прежнему расположению в корне проекта.

Desktop-first software prototype for a DIY Raspberry Pi Game Boy / Game Boy Color monoblock console.

Latest prepared firmware for the **actually connected RP2040**:
[native core + our menus, v2.2.3 test](firmware/releases/2026-10-07-rp2040-native-menu/README-RU.md).
The chip was verified by reading its factory boot ROM, not just the disk name.
This is a full Cortex-M0+ rebuild, not a bootloader replacement. Computer tests
passed; nothing was flashed automatically. Important: this native port has
1 MiB standard-ROM / 32 KiB cartridge-RAM limits and a new snapshot format;
the exact previous 2.2.2 rollback is provided beside the new UF2.

Prepared separately for a **real RP2350-Zero**, not the connected RP2040:
[native core + our menus, v3.0 test](firmware/releases/2026-10-07-rp2350-native-menu/README-RU.md).
It is rebuilt from the supplied RP2350 sources: profile B (CPU 200 MHz,
LCD request 100 MHz), original x2 320×288 DMA pipeline, our launcher/boot/pause,
I2S sound and five snapshot slots. Source archive and native B rollback are
beside the new UF2. Host/ARM tests passed; physical FPS/audio/panel stability
are not yet verified. Nothing was flashed automatically.

Previous **RP2040** firmware: [SHADOW FAST 2.2.2 test](firmware/SHADOW-FAST-TEST.md).
Its physical FPS improvement has not yet been verified. The current distribution
is in `firmware/releases/2026-09-28-shadow-fast-test/`, with two UF2 files:
`02-SHADOW-FAST-TEST.uf2` and the exact `01-PAUSE-SETTINGS-ROLLBACK.uf2`.
This build uses a SHA-pinned binary base plus preserved C/ASM addons, not a full
rebuild of `firmware/src/`. Source provenance is documented in
[Features v2](firmware/FEATURES-V2.md).

Cleanup on 2026-09-28 removed obsolete distribution bundles, repeated source
snapshots, old archives and generated previews to macOS Trash. One complete
pre-cleanup source archive remains at
`firmware/backups/source-shadow-fast-test-2026-09-28-compact.tar.gz`.
Intermediate UF2/ELF/BIN files referenced by build and regression scripts remain
as technical dependencies; they are not additional recommended firmware choices.
Historical documentation may refer to removed distributions. Games, save data,
source code and vendor dependencies were preserved.

Cleanup on 2026-10-19 moved generated object files, disassemblies/HEX, host-test
executables/debug symbols, temporary previews and Finder/Python caches to the
project-specific macOS Trash folder `ScarletPico-cleanup-2026-10-19`. ELF/BIN/UF2
technical dependencies, all current releases/rollbacks, CAD revisions and the
button-test models remain. The older full source archive was replaced by a
verified compact archive: historical sources and firmware were retained; SDK
files were omitted only when byte-identical copies remain in this workspace,
and generated preview media was excluded. The original archive is in Trash.
The compact archive therefore still depends on the retained SDK for identical
omitted files; it is not a standalone SDK backup. Audit: `cleanup-2026-10-19.json`
and its compressed detailed manifest. Trash was not emptied.

## Current hardware concept

The target device is now a fixed, non-modular monoblock console: a 480×320 display above physical controls in one rigid 3D-printed enclosure. The earlier detachable-module and folding-console ideas have been shelved, not deleted; see `docs/archive/modular-concept.md` and `docs/HARDWARE-CLAMSHELL.md`.

The browser build still shows the earlier one-piece 320×240 shell. Its emulator, ROM menu, input mapping, and save-state work remain useful; the physical mock-up will determine the final monoblock proportions.

## RP2040 hardware prototype

The native firmware is in `firmware/`. It targets RP2040-Zero,
ST7796 480×320, a shared-SPI microSD module, and eight direct GPIO buttons.
Version 0.9 keeps the vertical GB/GBC game menu and always upscales to 356×320,
with 62-pixel black sidebars. A second core sends separate small changed regions
while the first runs the emulator. It also fixes out-of-bounds muted-audio reads
and false frame timeouts during LCD-off loading. CPU stays at 125 MHz with the
existing freeze diagnostics; real-board speed/stability still need verification.
See `firmware/PACMAN-FIX-V09.md` for measured SPI traffic and limitations.
Audio is disabled. The current 2 MiB flash
layout fits 1 MiB ROMs, not 2 MiB ROMs. Actual FPS and stability still need
physical testing. The UF2 and
complete Mac/SD instructions are linked from `firmware/README.md`.

## Run

1. Put legally obtained `.gb` and `.gbc` files in `roms/`.
2. Run `npm start`.
3. Open `http://127.0.0.1:4173`.

The `roms/` folder simulates the future microSD card. ROM files and save data are excluded from Git. The current desktop build stores battery RAM and one quick-save state per ROM in browser local storage.

## Controls

- D-pad: arrow keys
- B / A: `Z` / `X`
- Start / Select: `Enter` / `Tab`
- Launcher: `Select` chooses the next game, `Start` launches it
- Quick save / load: `F6` / `F9`, or `Select+A` / `Select+B`
- Return to menu: `Esc`, or hold `Start+Select` for 1.6 seconds

## Emulator core

The desktop build vendors [binjgb](https://github.com/binji/binjgb), Copyright © 2016 Ben Smith, under the MIT License. See `app/vendor/binjgb-LICENSE`.
