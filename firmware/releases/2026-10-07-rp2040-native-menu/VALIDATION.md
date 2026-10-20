# RP2040 native 2.2.3 validation — 2026-10-07

## Passed on the computer

- Pico SDK 2.3.1 + ARM GCC 14.3.1: RP2040-Zero, Cortex-M0+, ARMv6-M/Thumb-1,
  standard `boot2_w25q080`, program `2.2.3-RP2040-test`.
- UF2 block framing, contiguous payload, RP2040 family `e48bff56`, initial
  stack/reset vector, flash/settings separation and SRAM/heap separation.
- Header of Peanut-GB-CGB and native LCD transfer functions match the incoming
  source ZIP. The existing bottom FPS label and menu drawing adapters are
  the only driver front-end additions. Rendering conversion and video worker also match, except
  iterating two buffers instead of three. The producer ownership transition
  was adapted explicitly to avoid waiting/overwriting DISPLAYING.
- Actual compiled ARM code under Unicorn Cortex-M0: menu, 64-entry navigation,
  unchanged idle screen, no repeated full-screen clear during selection,
  persisted volume/brightness, pause/resume order, confirmed exit, callback
  sanitisation in snapshots, fractional audio frame sample count.
- Actual ARM I2S startup/configuration: claimed DMA 3/4 (allocation mocked),
  RP2040 IRQ1 registers, PIO1 GP11/12/13, 16 kHz divider at 200 MHz,
  384-frame prefill, completed-half refill, LCD DMA register left intact.
- Actual ARM two-buffer transition: free, pending and busy-display cases;
  producer never overwrites DISPLAYING or waits for it to finish.
- Actual compiled ARMv6-M GB and GBC core: three frames of an original minimal
  test ROM in each mode; native RGB565 line callback writes the frame buffer.
- ASan/UBSan host tests: GB/GBC core 120 frames each, scaling bounds and RGB565;
  five snapshot slots with the RP2040 92160-byte staging capacity, backup
  recovery, CRC/ROM identity, corrupt/I/O/oversized state leaves live game intact.
- FatFs MBR first-partition tests at LBA 16 and 2048, read/save round-trip;
  no unsafe fallback to a phantom empty root at LBA 0.
- Zelda Link's Awakening, Aladdin GBC, Pac-Man GB: 1800 frames per game on host,
  valid scanline bounds, nonzero PCM, exact sample scheduling, no sanitizer error.

ARM tests mock hardware/SD, SDK ROM memory operations, hardware divider and
spin-lock acquisition. They do not emulate a physical panel or concurrent
electrical timing. Host game tests verify the unchanged core/APU, not RP2040 FPS.

## Not verified / not done

- No UF2 copied to the USB boot disk; no factory boot ROM replacement or patch.
- No physical FPS/audio quality test, sustained 200 MHz CPU / requested
  100 MHz LCD stability test, or power-loss/SD removal endurance test.
- No large-ROM streaming or old snapshot migration. This port accepts standard
  ROMs up to 1 MiB and cartridge RAM up to 32 KiB, not all GB/GBC cartridges.
- Rollback is SHA-pinned previous 2.2.2, not a newly read device flash backup.

## Re-run

Set `PYTHONPATH` to libraries containing Unicorn and pyelftools, and
`SCARLET_TEST_PYTHON` to their Python interpreter. On macOS the JIT runner
requires permission for executable mappings. Run from the project root:

```sh
bash firmware/tests/run_rp2040_native_tests.sh /path/to/zelda.gb /path/to/aladdin.gbc /path/to/pac-man.gb
```

Source ZIP contains the test scripts but not SDK, compiler, Python dependencies
or commercial ROMs. Hardware check used factory ROM magic, not the USB disk's
name alone; the connected board reported RP2040 ROM version 3.
