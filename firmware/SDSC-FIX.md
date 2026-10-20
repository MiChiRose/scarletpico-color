# SDSC compatibility repair — v0.3

The user's v0.2 photo shows `CARD INIT FAIL STATUS 01`. Inspection found an
unconditional rejection of non-SDHC cards in the bundled `pico-fatfs-sd`
revision `995777133afe98a2917bf45ffc7b488d10d62650`:

```c
if (SDCARD_V2HC != sd_card_p->state.card_type) {
    EMSG_PRINTF("SD Standard Capacity Memory Card unsupported\n");
    /* returns with STA_NOINIT */
}
```

This is a confirmed software incompatibility with a standard-capacity 2 GB
card, but the photograph alone does not establish the exact command that failed
on the physical prototype. The old interpretation that status 01 proves a
wiring fault was incorrect. No new formatting or wiring changes are required
to try the repaired firmware.

## Driver changes

- Accept SDSC v1 and v2 as well as SDHC/SDXC.
- Convert logical 512-byte sector addresses to byte addresses for SDSC at
  the command boundary: CMD17, CMD18, CMD24, CMD25, CMD32 and CMD33. Keep
  counters, range checks and contiguous-write state in logical sectors.
- Include `READ_BL_LEN` when decoding CSD v1 capacity. A 2 GiB card with
  native 1024-byte blocks has 4194304 logical 512-byte sectors.
- Reject byte-address overflow and out-of-range accesses, while allowing
  the final valid sector.
- Propagate a single-block data-write failure and a flush error.
- Treat ACMD41 timeout as failure even when its final R1 is idle rather
  than an explicit command error; preserve CRC-enable/OCR failures.
- Expose a small trace hook so diagnostics can display the initialization
  stage and last R1 response without drawing while the SD bus is active.

Local changes are in `vendor/pico-fatfs-sd`. Preserve them when updating the
dependency; `patches/pico-fatfs-sd-sdsc.patch` includes the driver changes and
the new compatibility header, relative to that vendor repository.

## Startup and display

The SPI pins/CS lines are prepared first, then SD initializes before display
traffic. The LCD stays deselected and in reset during that operation. Display
initialization no longer reinitializes the SPI peripheral after the SD driver
has claimed it. SD runs at 1 MHz after initialization. Diagnostic LCD SPI is
12.5 MHz. The panel's forced inversion is disabled; physical color verification
is still needed.

## Verification

`tests/test_sdsc.c` uses the actual driver headers. It tests SDSC v1/v2
read/write command addresses, unchanged SDHC/ACMD/non-address arguments,
overflow handling, CSD v1/v2 capacities, and access to the final sector.

```sh
cc -std=c11 -Wall -Wextra -Werror \
  -Ivendor/pico-fatfs-sd/src/sd_driver \
  -Ivendor/pico-fatfs-sd/src/include \
  tests/test_sdsc.c -o /tmp/scarletpico-test-sdsc
/tmp/scarletpico-test-sdsc
```

Both RP2040 UF2 targets compile. Host tests do not replace verification of
physical SD transfers or save writes. Diagnostic v0.3 is read-only: it checks
FAT, the ROM header, and the whole file. The supplied Zelda Rev.02 ROM is
524288 bytes, passes its header checksum, and has CRC32 `34D08E7B`.

Reference: [SD SPI initialization and byte/block addressing](https://elm-chan.org/docs/mmc/mmc_e.html).
