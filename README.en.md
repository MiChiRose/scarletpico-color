<p align="center">
  <img src="docs/assets/scarletpico-banner.png" alt="SCARLETPICO COLOR — the original pixel logo from the boot screen" width="960">
</p>

<p align="center">
  <a href="README.md">Русский</a> · <b>English</b>
</p>

<p align="center">
  <b>A handheld of our own. A custom enclosure. A big love for little games.</b><br>
  RP2040 · Game Boy / Game Boy Color · 3D-printed enclosure · Built for the love of it
</p>

<p align="center">
  <a href="docs/FLASHING.md">Flashing guide</a> ·
  <a href="docs/PINOUT.md">Pinout and wiring</a> ·
  <a href="hardware/case/LATEST.md">Printable models</a> ·
  <a href="DEVELOPMENT.md">Development</a>
</p>

## 🎮 The project

**ScarletPico Color** is a DIY handheld inspired by the Game Boy: a color
screen, a proper D-pad, physical buttons, a speaker, and games on microSD.
At its heart is a Raspberry Pi **RP2040** microcontroller on a compact
RP2040-Zero board—not a Linux single-board computer.

This is neither a commercial product nor a ready-to-assemble kit. It started
with the idea of building a console from scratch: soldering the electronics,
designing and printing the enclosure, and refining the buttons until they
feel right for “just one more game.” A passion project, shaped by test fits,
mistakes, and new revisions.

The handheld currently runs **Game Boy and Game Boy Color** games—handheld
systems from the 8-bit era. The RP2040 itself is a 32-bit microcontroller;
that does not imply support for every 16-bit console. NES, SNES, GBA, and
more powerful systems are not supported by the current firmware.

The next step is a move to **RP2350**. An experimental port is already
preserved in the project, but adapting it to the new board and testing it
on real hardware are still ahead. The current firmware targets RP2040 only.

<p align="center">
  <img src="docs/assets/case-front.png" alt="Render of the R3 front enclosure with D-pad and buttons" width="500">
</p>

*Rendered from the actual STL files: the R3 front, buttons, and a simplified
unpowered display. Colors are illustrative; this is not a photo of a finished unit.*

## What it can do

- **GB / GBC from microSD.** A game library, Russian and English UI,
  launching with A or Start, and rescanning without a reboot.
- **Saves.** Cartridge RAM saves and five save-state slots.
- **Audio.** A MAX98357A I2S amplifier, speaker, and adjustable volume.
- **Pause and settings.** Hold Start + Select to open the in-game menu
  for settings, saving, loading, and returning to the library.
- **On-screen battery monitor.** A battery icon and voltage in the menu
  and during gameplay, measured through GP29, a resistor divider, and a
  filter capacitor.
- **A custom boot sequence.** The pixel logo descends into the center
  of the screen with a short startup chime. Press Start to skip it.

Version **2.2.7** refreshes the library layout, avoids unnecessary redraws,
and reduces UI delays. These are menu improvements, not a promise of the
same FPS in every game. Compatibility and speed depend on the ROM and its
memory controller; the entire GB/GBC catalog is not universally supported.

<details>
<summary>Watch the actual boot animation</summary>

![ScarletPico boot sequence rendered by the firmware's ARM code](docs/assets/boot.gif)

Frames were captured by executing the ARM code with a simulated LCD, not
drawn separately for this README. The GIF is silent; on the device, the
game menu follows the boot sequence.

</details>

## Inside the handheld

| Component | Implementation |
|---|---|
| Processor board | RP2040-Zero, Raspberry Pi RP2040 |
| Display | 3.5″ SPI TFT, ST7796, 480 × 320 |
| Storage | microSD sharing the SPI bus with the display |
| Controls | 8 tactile switches: D-pad, A/B, Start/Select |
| Audio | MAX98357A over I2S and a small speaker |
| Power | Single-cell Li-ion/LiPo, protected TP4056 module, 5 V boost converter |
| Battery monitoring | GP29 / ADC3, two 4.7 kΩ resistors and a capacitor |
| Assembly | Perfboards and hand soldering; no custom PCB required |
| Enclosure | A custom adaptation developed from the original Tinkercad blank |

Connections, voltages, the SPI bus, buttons, audio, and the voltage divider
are covered in the **[pinout and wiring guide](docs/PINOUT.md)**. It also
identifies details that depend on the particular module and need checking.
The linked technical guides and some illustration labels are currently in Russian.

## 🛠 The enclosure

The enclosure evolved around the actual build: button positions, grip,
battery, display, speaker, and panel-mounted USB-C socket. Rounded edges,
a shallower upper rear section, and a smooth transition toward the lower
section make it comfortable to hold. Three shallow grooves on each side
add texture without extending the outline. The recessed lanyard attachment
also stays within the enclosure's footprint.

**Enclosure dimensions: 103 × 150 × 30 mm**, excluding protruding buttons.
Internal mounts use **M2 × 6 mm self-tapping screws for plastic**; the
stacked electronics assembly uses separate fasteners matched to its
existing spacers.

![One-piece R2 rear cover and the three R3 sections](docs/assets/case-rear-options.png)

| Variant | Why it is included |
|---|---|
| **One-piece R2 rear cover** | An earlier design without section seams. Kept for comparison; the raised area printed against supports had a rough finish. |
| **Three-piece R3 rear cover** | Upper section, curved transition, and lower section—three separate STL files. Splitting the cover allows different print orientations to reduce support marks. Each section attaches to the front enclosure. |
| **R3 front enclosure** | 3 mm LCD mounting posts, extra enclosure fastening points, display and speaker mounts, USB-C, power switch, recessed lanyard attachment, and side grooves. |
| **Button assembly** | Button caps and a shared retaining plate with thin flexures. A test fixture and the earlier separate retainers are also preserved. |

<details>
<summary>Look inside the front enclosure</summary>

<img src="docs/assets/case-inside.png" alt="Internal mounting posts and supports of the R3 front enclosure" width="500">

The display and speaker are secured by removable internal retainers rather
than glued to the enclosure. See the instructions for the relevant revision.

</details>

**What to print:** [current model list and caveats](hardware/case/LATEST.md).
**How to assemble it:** [R3 instructions](hardware/case/rev3-split/README.md).

R3 remains a fit-check revision. The shared button plate has known caveats
concerning the D-pad openings and the A-button spring length, documented in
the model list. One-piece R2 and split R3 parts should not be mixed at random:
choose a matched set. An attractive render is no substitute for checking
fit and button travel.

## ⚡ Firmware

Current file: **[ScarletPico 2.2.7 · RP2040 · UF2](firmware/releases/2026-10-20-rp2040-ui-polish/ScarletPico-v2_2_7-RP2040-UI-POLISH.uf2)**.

1. Turn the handheld off and disconnect its battery / external assembly power.
2. Hold **BOOT / BOOTSEL** on the RP2040-Zero and connect a USB data cable.
   Release BOOT once the **RPI-RP2** drive appears.
3. Copy the `.uf2` file to **RPI-RP2**, not to the microSD card. The board
   restarts and the drive disappears after flashing; this is normal.
4. Disconnect USB, restore the normal power supply, and check startup.

The **[full flashing guide](docs/FLASHING.md)** covers downloading the file
from GitHub, microSD setup, initial checks, and rolling back safely.

| Version | Purpose |
|---|---|
| [2.2.7](firmware/releases/2026-10-20-rp2040-ui-polish/README-RU.md) | Current UI update. ARM tests pass; full physical acceptance testing is still needed. |
| [2.2.6](firmware/releases/2026-10-20-rp2040-legacy222-battery/README-RU.md) | Previous working base with GP29 battery monitoring, available for rollback. |
| [2.2.2](firmware/releases/2026-10-07-rp2040-native-menu/01-ScarletPico-v2_2_2-RP2040-ROLLBACK.uf2) | Version verified on the handheld before battery monitoring was added. |

Do not flash RP2350 images onto an RP2040. Older experimental UF2 files
are kept for development history, not as recommended updates.

## Where the project is heading

- Refine fit and button feel through physical testing.
- Validate 2.2.7 on the assembled handheld: games, audio, saves, and battery monitoring.
- Bring the latest features to RP2350 and compare behavior on the new board.
- Simplify repeat builds and gradually move toward a unified, reproducible
  source-based build.

Suggestions for mechanics, ergonomics, the UI, and wiring are welcome.
Specific observations are especially useful: board model, enclosure revision,
firmware version, expected behavior, and what actually happened. For print
issues, include the material, part orientation, and a photo.

### Development

- [Sources, builds, and architectural limitations](DEVELOPMENT.md).
- [Current UI](firmware/ui-polish-addon/) and [battery monitor](firmware/battery-legacy-addon/).
- [Experimental RP2350 port](firmware/imported/scarletpico-rp2350-source/).
- [Firmware history](firmware/README.md) and [2.2.7 validation](firmware/releases/2026-10-20-rp2040-ui-polish/VALIDATION.md).

The current 2.2.7 build uses our C/ASM additions on top of a pinned binary
base; it is not a complete source rebuild of the historical emulator.
The base and build scripts are preserved. See the development documentation
for details.

---

ScarletPico is an independent hobby project and is not affiliated with Nintendo.
It uses a third-party emulation core; attribution and licenses are preserved
alongside the dependency sources. Game ROMs and save files are not included
in this repository.
