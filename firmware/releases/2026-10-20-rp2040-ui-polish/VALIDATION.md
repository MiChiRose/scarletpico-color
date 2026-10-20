# 2.2.7 UI polish validation — 2026-10-20

UF2 SHA-256: `2be5dd4d37001167a77501174ce02ba3d59a21e555b4ff6b87a2620b8c6f34c0`.
Exact rollback 2.2.6 SHA-256:
`e8c6c99223e571fd450ec213446bff1e702ce57671c3b994cbff59e9cbc92209`.
User reported 2.2.6 appears to work; new 2.2.7 still needs device acceptance.

## Binary audit

SHA-pinned RP2040 base, contiguous ordinary flash UF2, family e48bff56.
LCD init/transport, core/APU, clock code, original worker, optimized codec
and GP29 battery bytes are unchanged. Only explicit UI entries, boot call,
four UI debounce constants, BSS/heap limits, length/version metadata change.
33 changed base bytes; 2940 appended code bytes; 24 B RAM; zero new heap.
All old bytes outside the audited white list remain equal to 2.2.6.

## Executed ARM tests

`tests/test_ui_polish_arm.py` passed on the final image:

- Runs accepted 2.2.6 battery integration tests first, then loads 2.2.7.
- Real original pixel-font output for new library/header, with LCD writes
  captured into a framebuffer for QA. Page changes and every in-page focus
  transition match a full clean redraw: no stale outlines/text.
- 32 entries, last partial page, wrap to first page, invalidated cache,
  unchanged idle, EN/RU, long UTF-8 labels, empty/missing-folder/no-card.
- Original RU/EN Settings, About and five-row pause draw through the common
  new header without clipping/overlap. Preview PNGs visually inspected.
- Real settings loop with 12ms stable second read: short 4ms transient is
  rejected; volume 50→60 persists with one erase/program pair; reboot reads
  same settings; held B is consumed; read-only visit makes no flash write.
- New actual boot control flow completes in 1,448,000 modelled µs with
  unchanged logo/chime boundaries mocked. Held Start takes 30ms silent
  branch and consumes release. Logo positions are continuous and end at124.
- Relevant RGB565 text/background and focus contrasts are >=4.5:1.

Navigation traffic measured using actual old/new ARM draw calls, including
fills and text SPI rows: **43109 → 3222 pixels (-92.53%)** for adjacent rows
in the tested scene. Same idle selection sends zero pixels. Numbers are
not physical latency, bus-throughput or game-FPS measurements.

`test_video_heap_arm.py` on new `patched.bin` passed original allocator
startup/fallback tests (0/8/32/64/80KB cartridge allocations; 100KB OOM) and
repeated video release/reallocation with no leaks.

The unchanged game pipeline is proved by binary comparison, not a new
physical FPS benchmark. Peripherals and audio/logo playback boundaries
are modelled. No device was automatically flashed; no SD data changed.
