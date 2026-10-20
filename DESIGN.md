# ScarletPico Color Design

## Physical Firmware UI — 2026-09-28

This section supersedes older planning assumptions below for the working
hardware firmware. The present board is **RP2040-Zero with 2 MiB flash**;
the ST7796 screen is **480×320**, and the game fills its height at **356×320**
with 62-pixel black side rails. The actual completed LCD-update rate is displayed
as ` 40 FPS` at (8,310), at the bottom of the left rail. No LCD/EMU prefix.

The approved firmware UI uses the existing dark RGB565 palette, scarlet
selection outline, white pixel type and teal values. It is not the original
green browser mock. Settings contain language, volume, brightness, CPU
profile and About device. About is read-only, bilingual, and distinguishes
the actual menu CPU frequency from the chosen next-game frequency.

Start+Select held for 1.5 seconds opens a five-row pause menu: Resume, Save
state, Load state, Settings, Return to library. Settings reuses the same
bilingual page as the launcher. Volume and brightness can change without
unloading the current game; CPU changes still apply only at the next launch.
B returns to the selected Settings row in Pause; a second, separate B resumes.
Consume key release at page boundaries. Persist settings only while video/audio
workers are stopped and the watchdog is suspended. Keep five snapshot slots.

Upscaling remains nearest-neighbour from the native 160×144 frame to 356×320;
no high-resolution emulator framebuffer is created. Native pixel rows/columns
occupy two or three LCD pixels. Exact 2× (320×288) is not the default because
the user explicitly wants the entire 320-pixel screen height filled.

Moving focus redraws only the old and new rows. Changing page or language
may redraw the screen. No ambient animation, extra UI framebuffer, font
library or background microSD reads are introduced. Game rendering, sound
and timing remain outside the scope of visual menu changes.

Features v2.2 adds the explicitly requested boot-only signature: a scarlet
capsule enclosing SCARLETPICO descends to the screen centre in 1.8 seconds,
then COLOR appears and an original 400 ms two-note chime plays at the saved
volume. A short hold leads to the library (or the existing missing-card screen).
Start skips it, including a static/silent start when held at power-on. Only
the sprite's old/new bounds are repainted; the animation is never a game-loop
task. The existing PCM scratch is shared sequentially with the scanline renderer.

## Current Hardware Direction

ScarletPico Color is a single, non-modular monoblock console with one rigid enclosure. The display, controls, battery, processor, microSD, audio, power circuitry, and mechanically supported solderable prototyping boards are all fixed in the same body.

Both the detachable-module concept and the later clamshell concept are shelved. The clamshell was rejected for the first hardware revision because a reliably indexed hinge would add play, fragility, cable fatigue, and mechanical complexity. Its notes and render remain as archived design research.

## Theme

A DIY monoblock console seen on a dark electronics workbench. The shell carries the scarlet identity; the menu recalls a reflective DMG LCD; games render in their native color space inside a black technical frame.

## Color

The product uses a restrained dark environment, a scarlet shell, an indigo system anchor, and a four-tone reflective LCD palette. CSS tokens are defined in OKLCH in `app/style.css`.

## Typography

System sans is used for the desktop guide. Compact monospace text is used inside the 320×240 display to reflect the constraints of the future embedded build. The boot wordmark uses a rounded italic system face but remains an original ScarletPico composition.

## Motion

The wordmark descends vertically during the 3.4-second boot sequence and lands with a three-note original chime. All interaction transitions remain under 200ms. Reduced-motion mode shortens startup to 700ms.

## Layout

The physical display target is 480×320 in landscape orientation. During gameplay, the 160×144 Game Boy image scales by an exact factor of 2 to 320×288. This leaves 80-pixel side rails and 16-pixel top/bottom margins for black framing and compact status information without distorting pixels. The existing 320×240 browser shell remains a software prototype until the clamshell UI is redrawn.

## Physical Layout

- Upper area: 3.5-inch 480×320 ST7796 display and its mechanically supported bezel.
- Lower area: D-pad or four direction buttons, A, B, Start, Select, and the two joined prototyping boards.
- Internal area: processor board, microSD module, audio circuitry, battery, charging and power conversion.
- There is no hinge or flexing display interconnect in the first hardware revision.
- The two prototyping boards must be screwed to internal posts. Their soldered joint must not carry button-press loads by itself.

The exact placement is provisional until the component photograph and measured dimensions are available.

## Electrical Direction

- One RP2350 is the sole processor. The fixed controls connect directly to GPIO; module-identification buses and auxiliary RP2040 boards are no longer required.
- Each button connects a GPIO input to ground and uses a pull-up. Firmware performs debouncing.
- The display uses SPI with DMA. Game Boy timing remains approximately 59.7 Hz; display transfers may present every second emulated frame if bandwidth requires it.
- The microSD and display may share an SPI bus only with separate chip-select lines and verified module voltage levels. Separate SPI controllers are preferable if the final pin allocation permits.
- Battery charging, protection, power-path behavior, amplifier, headphone switching, and battery measurement remain to be finalized from the exact purchased modules.

## Components

- Power screen: explicit gesture required so browsers may start audio.
- Boot screen: original capsule wordmark and chime.
- ROM menu: microSD inventory with D-pad selection and A activation.
- Game frame: integer-scaled emulator viewport with battery status; no real-time clock is required.
- System feedback: short save/load notices that do not obscure the game center.
