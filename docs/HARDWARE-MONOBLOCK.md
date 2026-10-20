# Monoblock Hardware Plan

Status: current direction as of 2026-09-26.

## Architecture

ScarletPico Color is one fixed, non-modular console in a rigid 3D-printed enclosure. The 480×320 ST7796 display has already passed image and animation tests with the processor board. The first control prototype uses eight physical buttons soldered to supported prototyping boards.

## Button wiring

Each normally-open button connects between one GPIO and common ground. Firmware enables the GPIO's internal pull-up, so the signal is active-low:

- released: logical high;
- pressed: logical low.

The current RP2040-Zero wiring draft assigns Up GP0, Down GP1, Left GP2, Right GP14, A GP15, B GP26, Start GP27, and Select GP28. These assignments must not be transferred blindly to a different RP2350 carrier without checking its actual header pinout.

For a four-leg tactile switch, the two legs on each side are commonly connected internally. Use one leg from each opposite side and confirm it with a continuity tester before soldering.

## microSD

The 2 GB card should use a single MBR partition formatted as FAT16 for maximum compatibility with embedded FAT libraries and the SD capacity standard. exFAT requires optional filesystem support and is unnecessary for Game Boy ROM sizes.

Proposed structure:

```text
/roms/zelda.gb
/saves/
```

## Power warning

Do not build the current PDF's USB-diode/TP4056 common-point circuit without revision. Tying the diode-fed USB rail and TP4056 battery output directly together can create an uncontrolled reverse charging path. Button and signal wiring can be prototyped from USB power while a proper charger/load-sharing circuit is selected.

## Archived concepts

- `docs/archive/modular-concept.md`: detachable modules.
- `docs/HARDWARE-CLAMSHELL.md`: folding enclosure.
- `docs/concepts/scarletpico-clamshell-concept-v1.png`: clamshell appearance render.
