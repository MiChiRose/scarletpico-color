# Validation — 2026-10-07

Result: build and computer tests passed. **The merged firmware has not been
flashed or tested on the physical console.** No measured hardware FPS gain is claimed.

## Artifact identity

- Merged UF2 SHA-256: `1abe1d0a76ded712f401ecec400c6920ae624fd456a5c01f1af0db5a62cb586c`.
- Original B rollback SHA-256: `168d797c856a7a8651c5a1795ac0822b303f4af3f56920f18dbf0581ddc73761`.
- Incoming source ZIP SHA-256: `1e1e2f7ed8bcf15b4f42bfdd1b7c2cf89403e734c26124986d4f5f54a4d312ba`.
- Unchanged Peanut-GB header SHA-256: `6244f56ee63933987b4bbfb7401c1ddef9d8e2610b9a78a882776e785631e551`.

Official picotool file inspection: RP2350 ARM Secure, Waveshare RP2350-Zero,
SDK 2.3.1, release build, version `3.0-RP2350-test`; image metadata chain closes.
Flash ends at `0x100207d4`, before settings at `0x1007f000` and ROM cache at
`0x10080000`. BSS ends at `0x200661dc`, below stack/heap limit `0x20080000`.
Hot core functions are in RAM. All UF2 image blocks use the RP2350 family;
the single ignored absolute-family block is the SDK bootloader metadata block.

## Source preservation

The kernel header is byte-identical to the incoming source archive.
Function bodies compared without changes: `display_frame`, `window`,
`send_row`, `bus_idle`, `finish_window`, `display_game_speed`, `display_sd_speed`,
`display_init`, `publish_frame`, `video_worker`, `draw_line`.
This does not assert that the compiled firmware is byte-identical: SDK,
integration and sound differ. See `build-audit.json` and `MERGE.md`.

## ASan/UBSan host tests

- Supplied core test: 120 GB + 120 GBC frames, RGB565 and scaling checks.
- Five snapshot slots: core/RAM/APU round-trip, corruption fallback,
  ROM identity, write/read failures, invalid files, staging-capacity rejection;
  failed loads do not mutate the current game.
- SD/FatFs regression: stale FAT16 metadata at LBA 0 reproduces the old
  empty-root/ROMS-not-found failure; explicit first MBR partition at LBA 16
  and 2048 passes ROM read and save round-trip. Missing partition is rejected.
- Shared UI: dirty regions, idle no-op, range/clipping, settings persistence,
  loading/card/empty/error pages. The shared renderer can still display Russian
  text, but the new native front end exposes only English.
- Actual ROMs, 1800 frames each with sound: Zelda Link's Awakening (U, v1.2),
  Aladdin (U, GBC), Pokémon Crystal (UE, v1.1), Pac-Man (U, Namco Hometek).
  Bounds and PCM checks passed, with no sanitizer findings.

## Compiled Cortex-M33 integration tests

Unicorn executes the final ELF; peripheral/SD operations are stubbed.

- Our menu, 192 entries, no full redraw on selection, no redraw while idle.
- Settings volume/brightness, actual PWM register writes, reserved flash sector
  persistence and simulated reboot.
- Start+Select filtering, 1.5-second pause hold, audio/video stop-resume order,
  release consumption, explicit exit confirmation, no automatic relaunch.
- Actual native snapshot structure and callback-pointer strip/restore.
- PCM mixing at 0/50/100%, exact fractional samples for 59.7275 Hz GB frames.
- Claimed audio DMA 3/4, DMA IRQ2, I2S 16 kHz divider, 384-frame prefill,
  completed-half refill; display DMA canary remains unchanged.

## Not established by these tests

Physical FPS, overclock stability, SPI signal integrity, real SD timing,
audible quality/underruns, real panel orientation, battery operation and
long-run play. Host smoke tests do not prove all ROMs work. Native timing and
core behavior are retained; no universal crash/freeze guarantee is made.

The earlier unreleased binary-only integration prototype was removed from
the release folder and retained under `firmware/build-rp2350-menu/superseded/`.
Old working RP2040 releases and user files were not deleted.
