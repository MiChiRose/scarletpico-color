# v0.8: full-height image and freeze investigation

## User requirements and observed fault

The user wants every GB/GBC image to fill the display height, preserving the
aspect ratio and leaving black sidebars. They also confirmed that v0.7 can
freeze at different points in gameplay and Start+Select then does not return
to the menu. This is not explained by a low display update count alone.

The physical freeze has not been reproduced here. No serial device was
connected during this investigation. The changes below mitigate identified
risks and gather evidence; they do not establish that the board's fault is fixed.

## Display

- Native GB/GBC frame: 160×144; output: 356×320 centered on 480×320.
- Left/right bars: 62 pixels each. There are no top/bottom bars or cropped rows.
  The ideal width is 355.56 pixels; 356 is the nearest integer, a 0.125% aspect
  rounding difference. Nearest-neighbour scaling keeps pixel colors sharp;
  because the scale is fractional, source pixels occupy two or three LCD pixels.
- Size selection was removed from the menu. Both games always fill the height.
- FPS labels moved into the left black sidebar; they never cover gameplay.
- Two producer/consumer framebuffers are retained. An optional separate 46,080
  byte buffer records the last completed image. Exact comparisons find the
  changed source bounding rectangle, map it into output coordinates with ceil
  boundaries, and send only that rectangle. Identical frames send no image data.
- The first image after every game launch is a full redraw. Cache allocation
  failure falls back to full redraws; mandatory-buffer allocation failure is
  reported. Both allocations and frees occur while the second core is stopped.

At the current 12 MHz game SPI clock, a complete 356×320 RGB565 image is
227,840 bytes, taking at least 151.89 ms (below 6.6 full-image updates/s before
overheads). Upscaling does not preserve the bandwidth benefit of a tiny output
window. Partial updates help static backgrounds and small changes, not guaranteed
full-scene scrolling speed. LCD FPS counts non-empty image updates, not panel
scan frequency; an unchanged scene can correctly show zero LCD FPS while EMU
is running. The most recent video-job time includes comparison plus transmission.

ST7796 address-window and RAMWR behavior is documented in the
[controller datasheet, sections 9.2.20–9.2.22](https://files.waveshare.com/wiki/common/ST7796S_Datasheet.pdf).
SPI rate, RGB565 format and landscape orientation remain at their working values.

## Freeze risks addressed

1. **CPU overclock:** v0.7 runs games at 250 MHz / 1.20 V. The primary v0.8
   build uses 125 MHz and no raised voltage. 250 MHz is not the stock setting;
   the [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
   describes 133 MHz operation, with newer notes permitting 200 MHz at 1.15 V.
   Stock-clock testing distinguishes some timing/power-sensitive failures but
   does not prove that the old overclock caused this user's freeze. The separate
   `oc250mhz` image is experimental and can be unstable. Both display geometry
   and freeze checks are identical in the two builds; 125 MHz may emulate slower.
2. **Unbounded frame wait:** upstream `gb_run_frame` loops until virtual VBlank.
   A ROM CPU loop with LCD disabled can prevent it returning. The wrapper now
   limits the outer loop to 200,000 CPU steps and reports `FRAME TIMEOUT PC ...`
   rather than freezing there forever. This is a guard, not a compatibility
   fix; a legitimate unusually long LCD-off routine can also hit the limit.
   An internal HALT wait is covered by the watchdog, not this outer step limit.
3. **Whole-loop stalls:** an eight-second hardware watchdog is armed only for
   active game clock/video/emulation work. Core 0 feeds it only while the video
   worker is healthy. A pending video job older than two seconds is unhealthy;
   core 0 records VIDEO WAIT and stops feeding. Stalls can reboot after roughly
   8–10 seconds, leaving a report with last stage, last known emulated PC and
   CPU clock. These are breadcrumbs, not a stack trace or verified fault address.
4. **Allocation failure:** Pico SDK normally panics when malloc fails, before
   the application's NULL handling can run. `PICO_MALLOC_PANIC=0` enables the
   existing errors and optional-cache fallback instead. This load-time risk is
   real but is not evidence for the user's mid-game freeze with Aladdin/Zelda.
5. **USB logging stalls:** reduced the SDK's USB stdout wait from 500 ms to 2 ms
   and stdio lock wait to 10 ms. Unread logs may be dropped rather than causing
   large recurring delays. This is not proof of the reported permanent freeze.

### Watchdog limitations and saves

`RECOVERED FROM FREEZE` waits for A after reboot, allowing a photo. Unsaved
progress is lost on reset. The guard is disabled during flash ROM caching and
temporarily paused during SD saves: the current save implementation overwrites
the destination and is not transactional, so forcibly resetting in that critical
section could corrupt the existing save. SD driver timeouts remain in effect,
but the guard does not recover a permanent SD-write deadlock. User button-release
waits keep feeding; waiting for a button is not treated as a crash. There is no
claim of coverage for brownouts, wiring faults or all hardware failure modes.

## Software verification

- Production driver with SPI simulation: correct full-height mapping, every
  output pixel, bottom/right edges, 62-pixel sidebars, 100 sparse image changes,
  identical-frame skipping, full-redraw fallback and no FPS overlap with game.
- Production concurrent worker: 242 transfers, 24 regular start/stop cycles,
  buffer ownership, busy rejection, simulated stuck-worker health detection,
  unchanged frames not counted as LCD updates, mandatory/optional allocation
  failure and cleanup. AddressSanitizer/UBSan and separate ThreadSanitizer runs.
- Freeze-guard tests: timeout settings, stage/PC/clock persistence, one-shot
  recovery report, healthy-only feed, pause/resume around SD writes, and no
  false report for a manual reset. Hardware reset behavior still needs board testing.
- Synthetic homebrew ROM reproduces LCD-disabled endless execution and now
  returns `FRAME TIMEOUT`; an invalid opcode returns `CORE ERROR`.
- Launcher tests retain chosen-ROM launch, no autostart, full-height fixed
  despite Left/Right, Start+Select suppression/cooldown, SD/LCD exclusion and
  watchdog disabled for SD writes/flash caching.
- Each actual supplied Aladdin and Zelda ROM passes 1,800 normal frames,
  1,800 with 3/4 render skipping (same final pixels and SRAM), a 120-frame reload,
  then 18,000 more frames with deterministic movement/actions and render skipping.
  These are host tests, not a physical-board stability measurement.
- Existing SDSC, MBR, library and display regression tests remain enabled.

## Flash and test

1. Use `scarletpico-rp2040-full-height-v0.8-125mhz.uf2` first. BOOT + connect
   USB, then copy to RPI-RP2. Keep the same SD card and wiring. This is RP2040,
   not RP2350. The menu should say V0.8 and 125MHZ.
2. Play the same Aladdin or Zelda scene where v0.7 froze. Verify the image
   reaches top and bottom and controls/Start+Select work. Expect lower CPU
   performance at stock clock; record both sidebar FPS values during gameplay.
3. If it freezes, wait about ten seconds without removing power. Photograph
   `RECOVERED FROM FREEZE` or `EMULATOR STOPPED`, including every line.
4. If no recovery screen appears, report whether the screen remained lit and
   whether the Mac still detects USB; this points beyond the guarded paths.
5. Save through the game's own menu and return to the launcher before power-off.
   Do not flash the experimental 250 MHz build until the stock comparison is useful.

Build default: `SCARLET_GAME_CLOCK_KHZ=125000`; experimental: `250000`.
Old v0.6 and v0.7 release files are preserved for rollback/history.
