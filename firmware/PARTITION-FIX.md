# v0.5: explicit MBR partition selection

## Evidence

On 2026-09-26 macOS reported an MBR card with one FAT32 partition, starting
at byte 8192 (LBA 16), with `roms` and `saves` in its root. The Zelda file was
verified and a short-name copy, `roms/zelda.gb`, was added without removing
the original files.

The later diagnostic v0.4 hardware photo instead shows:

```text
INIT 00 TYPE SDSC V2
MOUNT CODE 0 FS 2 LBA 0
ROOT BEFORE 0 COUNT 0
ROMS BEFORE CODE 4
ZELDA BEFORE CODE 5
ROOT AFTER 0 COUNT 0
ROMS AFTER CODE 4
ZELDA AFTER CODE 5
```

FatFs type 2 is FAT16, not the FAT32 volume macOS opened. These results are
already present before LCD initialization. An empty directory on the wrong
volume does not establish that the actual `roms` folder is missing.

FatFs auto-detection accepts a valid-looking FAT boot record at sector 0
before looking for partitions. Old FAT metadata surviving in an MBR's boot
area can therefore cause this exact result. This mechanism was reproduced
in a synthetic fixture; raw sectors from the user's actual card were not
captured, so their precise contents remain unverified.

## Change

- Enable `FF_MULTI_PARTITION` in the vendor FatFs configuration.
- Link `src/partition_map.c` into both firmware targets. Volume `0:` maps to
  physical card 0, MBR partition 1. Its offset is read from the partition
  table, not hard-coded to 16.
- Use explicit `0:` paths for the game mount, ROM, and save folder/file.
- Reject missing partition 1 rather than silently falling back to a stale
  whole-disk filesystem. Cards must use an MBR with a FAT16/FAT32 first
  partition; unpartitioned FAT is no longer accepted by this mapping.

The vendor configuration delta is preserved in
`patches/pico-fatfs-sd-mbr.patch`. It complements the earlier SDSC driver
patch; both are needed for this prototype.

## Regression test

`tests/test_partition_mount.c` links the actual production FatFs sources and
partition map against an in-memory sector backend. It never opens a device
or writes to a physical card.

The test verifies:

1. Auto-detection reproduces FS2/LBA0, an empty root, ROMS=4, and ZELDA=5.
2. Explicit partition selection mounts FAT32 at LBA16, finds the ROM, and
   reads it across non-contiguous clusters.
3. Save creation, sync, reopening, and byte verification succeed; no writes
   occur outside the selected partition.
4. LBA2048 and a clean MBR also work, without depending on offset16.
5. A missing MBR partition is rejected instead of selecting stale FAT.

Run from the project root (the explicit CLT paths avoid the system Xcode
license shim on the development Mac):

```sh
/Library/Developer/CommandLineTools/usr/bin/clang \
  -std=c11 -Wall -Wextra -Werror \
  -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk \
  -Ifirmware/vendor/pico-fatfs-sd/src/include \
  -Ifirmware/vendor/pico-fatfs-sd/lib/fatfs/source \
  firmware/tests/test_partition_mount.c \
  firmware/src/partition_map.c \
  firmware/vendor/pico-fatfs-sd/lib/fatfs/source/ff.c \
  firmware/vendor/pico-fatfs-sd/lib/fatfs/source/ffsystem.c \
  firmware/vendor/pico-fatfs-sd/lib/fatfs/source/ffunicode.c \
  -o /tmp/scarletpico-test-partition
/tmp/scarletpico-test-partition
```

All cases passed. Both RP2040 UF2 targets compiled successfully. This is
host-side software verification, not a successful run on the user's board.

## Hardware follow-up

The existing card does not need reformatting or another ROM copy. Flash the
v0.5 game build, power off fully for five seconds, then boot with the card
inserted. The initial orange ROM-cache screen is expected.

If needed, v0.5 diagnostics should show `MOUNT CODE 0 FS 3 LBA 16` for this
card, followed by `RESULT SD AND ROM READ OK`. The expected full Zelda ROM
CRC32 is `34D08E7B`. The diagnostic is read-only. Actual ROM boot, save
persistence, display timing, and the physical SPI link still need hardware
validation.
