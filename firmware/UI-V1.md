# ScarletPico Color — UI v1

Firmware: [scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1.uf2](releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1.uf2)

For the existing **RP2040-Zero + 480×320 ST7796 + MAX98357A** wiring.
This is not an RP2350 build. Use the same BOOTSEL/UF2 procedure as the working audio50 release. No new Mac drivers, libraries, ROM conversion or microSD formatting are needed.

## Controls

| Screen | Controls |
| --- | --- |
| Game library | Up/Down or Select: choose; A/Start: play; Right: settings; B: rescan |
| Settings | Up/Down: choose; Left/Right: adjust; B: return and save |
| Missing/unreadable card | A: retry; Right: settings; or power off, check card and restart |
| In game | Unchanged, including the existing Start+Select return-to-menu gesture and release cooldown |

Settings apply immediately and are persisted when leaving with B:

- Language: English or Russian. Game ROMs themselves are not translated.
- Volume: 0–100%, in steps of 10. Default 50%; 0 is mute.
- Brightness: 10–100%, in steps of 10. Default 100%; cannot reach zero.

Brightness uses **LCD BL on GP10**, active-high PWM, slice 5/A. It cannot control a backlight connected directly to a power rail. The PWM does not use interrupts, DMA or change system clocks. The audio connection remains BCLK GP11, LRC GP12, DIN GP13.

## Screens and redraw behavior

The approved dark/scarlet pixel style is shared by the library, settings, loading and error screens. Latin/Cyrillic glyphs are rendered by code, not as a generated full-screen bitmap. The muted text was lifted slightly for contrast.

- Moving within the library page updates the old/new rows and the selection information. Changing pages updates the list area, not the header or footer.
- Moving in settings updates two rows. Adjusting a number updates only its value and meter. At a limit there is no redraw. Switching language redraws the text area, leaving the header intact.
- An idle menu or error screen performs no periodic redraws.
- Loading shows the game title and a centered spinner. Only eight small spinner blocks are refreshed, at most ten times per second. It updates between ROM reads and aligned flash-erase chunks, without a competing SPI task/ISR. A blocking card transaction or erase chunk can briefly pause the animation. A cached game launches without an artificial delay.
- Missing/unreadable cards have a stable error screen and an explicit retry. A readable card with no `/roms` directory or no games gets a separate empty-library message. No ROM starts automatically.

## Preserved working firmware

The build appends the UI to the exact, user-tested audio50 image, rather than rebuilding the unrelated older `src/main.c` snapshot.

Base SHA-256:
`692a06aeea11e97b0b03f29418703e024ac91deaeb26f0e9a2eebc05e8e07907`

The emulator, game rendering/scaling, frame pacing, audio synthesizer, I2S/DMA implementation and clock configuration are byte-identical to that base. Only the mixer's fixed-volume load is redirected to a validated 0–100 value. The working CPU/LCD/SD settings remain unchanged: 200 MHz game CPU, 50 MHz requested LCD SPI and 12.5 MHz requested SD SPI (the existing filename abbreviation remains `sd12`). These are the existing experimental hardware speeds, not a new stability guarantee.

Additional static RAM: **992 bytes**, chiefly one text scanline, no UI framebuffer and no heap allocations. Each binary hook and changed byte is recorded in the adjacent release JSON. Original game/save routines and ROM cache addresses are retained. ROM loading adds cooperative progress drawing; aligned 64 KiB erase chunks cover exactly the original erase range.

## Settings persistence and safety

A 16-byte versioned record occupies a reserved internal-flash sector at offset `0x7F000..0x7FFFF`, below the existing ROM cache at `0x80000`. The UF2 does not contain this sector, so future UI reflashes preserve preferences. No microSD files are modified by saving console settings.

Only changed preferences are written, once on B-exit, with the game/audio/video workers stopped. A failed or interrupted settings write is rejected at boot and falls back to English, volume 50 and visible brightness 100. This small record is intentionally separate from game saves and works even when no card is inserted. If verification fails, the settings screen reports that the changes are only active until restart.

Do not remove or insert the card with power connected. If card access fails during a game save, the existing save-error/retry behavior is retained; removing a card cannot be made safe by a menu graphic.

## Build and verification

```sh
/Library/Developer/CommandLineTools/usr/bin/python3 firmware/tools/build_ui_addon.py
bash firmware/tests/run_ui_tests.sh
```

Uses the existing Pico SDK/toolchain configuration and exact pinned base UF2. The generated UI sources are in `ui-addon/`; the real hardware shim, short-enum ABI assertions and register-preserving assembly bridges are kept separately from the portable UI renderer.

`tests/test_ui_arm.py` needs Unicorn, Capstone and pyelftools. It executes the final Thumb code, mocking only hardware/FatFs services. Tests cover PWM limits, actual mixer output at 0/50/100%, settings persistence, no-card retries, ROM/cache integrity, SPI handoff, inline-hook register/flag preservation, and the **original main loop** through selection/settings/launch. Native renderer tests use ASan/UBSan and assert dirty-region bounds; screenshots are generated from that same C renderer under `build-ui-addon/previews/`.

Short actual-ARM ROM smoke tests passed for Zelda GB and Aladdin GBC, 120 frames each, with sound. This is not a physical-device FPS, electrical-brightness or long-duration stability test. This release has not been automatically flashed to the console.

Rollback: [unchanged working audio50 UF2](releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-audio50.uf2).
