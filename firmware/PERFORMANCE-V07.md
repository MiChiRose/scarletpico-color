# v0.7: native-size output and concurrent video

## What changes

This build is for the existing RP2040-Zero, ST7796 480×320 display and shared
SPI microSD wiring. GB/GBC support, ROM selection, saves and the successful
SDSC/MBR fixes are retained. No rewiring, card formatting or ROM renaming.

v0.6 transferred a 320×288 RGB565 image synchronously, blocking game execution
for at least 122.88 ms at the actual 12 MHz SPI clock. Its scheduler also waited
33.333 ms after each transfer before considering another. This was a direct
display bottleneck, independent of whether the emulation core could go faster.

v0.7 uses the following selectable sizes:

| Menu choice | Game image | Pixel bytes per frame | Payload time at 12 MHz |
|---|---:|---:|---:|
| FAST (default) | 160×144 | 46,080 | 30.72 ms |
| BALANCED | 240×216 | 103,680 | 69.12 ms |
| LARGE | 320×288 | 184,320 | 122.88 ms |

These times are calculated lower bounds, not measured frame rates. Commands,
CPU work, scheduling, overlays and SD writes add overhead. Four times fewer
bytes does not promise four times the end-to-end FPS. All sizes preserve the
game's aspect ratio and are centered with black borders. The panel does not
automatically enlarge a small submitted frame; FAST is physically smaller.

The menu's Left/Right controls change size, not the game selection. Up/Down
or Select still chooses a ROM; A or Start launches it. The size choice remains
in RAM until power-off and applies to both GB and GBC. In-game directions are
not repurposed. Hold Start+Select for 1.5 seconds to save and return to the
menu; the two-second cooldown plus full button release remains in place.

## Processing and memory

- Core 0 runs the emulator, samples controls, and produces RGB565 frames.
- Core 1 owns the SPI display transfer and periodic FPS overlay.
- Two 46,080-byte framebuffers prevent concurrent writes into a frame being
  transmitted. A release/acquire atomic handshake publishes each frame.
  There is at most one in-flight frame and one prepared frame. The next image
  is rendered while the preceding one is transmitted, then submitted as soon
  as SPI is free, including between emulation ticks. The queue cannot grow.
- When both buffers are occupied, the next emulated frame still executes,
  including CPU, timers and game logic, but the core omits pixel generation.
  This is render skipping, not slowing game logic to the display refresh rate.
- The old post-transfer delay is removed. Emulation is paced at 16,743 µs per
  frame when CPU capacity permits; this does not guarantee real-time GBC speed.
- Text drawing now batches each glyph into one LCD address window instead of
  a transaction for every individual font pixel.
- SPI stays at the proven 12.5 MHz request / 12 MHz game clock; CPU stays at
  the existing 250 MHz / 1.20 V game setting. No further overclock is introduced.

The second buffer is dynamically allocated after the game's save RAM. If
allocation fails, the launcher reports an error rather than corrupting RAM.
The supplied Aladdin (0 save bytes) and Zelda (8 KiB save RAM) fit the static
and dynamic memory budget. Large-save cartridges may not fit. Both core stacks
are 4 KiB. Static ELF BSS is 117,016 bytes; firmware ends at flash offset
0x2ccf0, safely below the 512 KiB ROM-cache boundary.

SD and LCD share SPI0. Every in-game save waits for video completion before
touching SD; core 0 cannot publish another frame during that operation. UI
messages also wait. On return/error, core 1 acknowledges a parked state before
reset, avoiding resetting it while it owns an SDK atomic lock. It is stopped
before any CPU clock change or ROM-cache flash erase/program. This matters
because executing core 1 from flash during flash programming is unsafe.

## FPS display and diagnosis

The bottom black border shows `LCD … FPS` and `EMU … FPS` about once a second:

- LCD: completed transfers per elapsed second.
- EMU: complete emulated frames per elapsed second, including non-rendered ones.

The first second may show EMU 0 until a measurement is available. The values
are integer, short-window estimates; a one-FPS fluctuation is normal. USB
serial also logs average emulator work time per frame and the most recent LCD
transfer time. EMU near 60 with lower LCD means the game can run near real time
but display bandwidth is limiting. Low EMU as well means CPU/game workload is
also limiting. The overlay is a diagnostic feature of this prototype.

## Verification on the Mac

`bash firmware/tests/run_host_tests.sh` passed with AddressSanitizer and UBSan:

- Existing SDSC addressing/capacity and MBR partition regression tests.
- Actual display-driver SPI simulation: every output pixel, all three sizes,
  centering, borders, RGB565 byte order, text batching/clipping, chip-select
  exclusion and the unchanged conservative SPI request.
- Actual video worker on concurrent pthreads: 240 transfers and 24 complete
  start/stop cycles across all scales. Producer writes do not modify the
  in-flight buffer; submitting while busy is rejected. This test also passed
  a separate ThreadSanitizer run with no race report.
- Actual launcher with mocked hardware: no automatic ROM launch, chosen game
  and scale, held-button cooldown, continued emulation while LCD is busy,
  chord suppression, save/SPI exclusion, and stopped video at flash/clock changes.
- Real local Aladdin and Zelda ROMs: 1,800 fully rendered frames compared with
  1,800 frames where 3/4 of pixel generation is skipped. Identical inputs
  produce identical final frame pixels and save RAM. A fresh 120-frame reload
  also passes for each ROM. ROM files are not included in firmware or Git.
- RP2040 release UF2 builds successfully; `picotool` identifies family RP2040,
  program version 0.7, Pico SDK 2.3.1. The earlier v0.6 UF2 remains untouched.

These tests validate software behavior, not physical performance. v0.7 has
not yet been flashed or measured on the user's board by this task.

## Hardware acceptance

1. Exit the old game to its menu so cartridge RAM is saved, then disconnect
   power. Hold BOOT while connecting the RP2040-Zero by USB.
2. Copy `releases/scarletpico-rp2040-gb-gbc-menu-v0.7.uf2` to `RPI-RP2`.
   This is an RP2040 image, not an RP2350 image.
3. Boot with the same SD. Confirm menu V0.7 and FAST 160X144.
4. Launch Aladdin, enter gameplay, and photograph the bottom FPS line after
   10–15 seconds. Check that the entire image is stable, centered and in color.
5. Return using Start+Select, release the buttons and wait for the cooldown.
   Choose BALANCED with Right, relaunch and compare in the same game scene.
6. Repeat with Zelda; check controls and the game's own save, return to the
   menu before powering off, then verify that the save reloads.
7. Repeatedly switch Aladdin → Zelda → Aladdin to exercise flash caching,
   core stop/restart, SD access and memory reuse. Do not unplug during LOADING.

Cartridge SRAM saves are still not emulator save-states; Aladdin's supplied
cartridge has no save RAM. Sound and crash-safe transactional save writes are
not part of this performance update.
