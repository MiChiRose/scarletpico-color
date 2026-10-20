# v0.9-B sound-only extension

This build adds MAX98357A sound to the user's exact working UF2. It does NOT
rebuild the launcher from the newer local v0.10 source.

Base: `audio-addon/base-v0_9-B-200mhz-lcd50-sd12.uf2`.
SHA-256: `6d8dda2c26f1f909d47b913bcf5ad6caa92777a89fa3842916fbfc8edb88aad2`.

## Preserved

- All original CPU, LCD and microSD frequency settings, including overclocking.
- The complete original custom menu, artwork, text and controls.
- Game scaling, frame scheduling, library handling and saves.
- The original version string. Identify the sound image by its `audio50` filename.

The patcher validates the entire base SHA, every replaced instruction, the RAM
budget and flash-cache boundary. Every original byte outside its small audited
audio-hook/memory-metadata ranges must match. The adjacent release JSON records
the exact ranges and output SHA. The original 200 MHz/LCD 50 MHz experimental
settings retain their original hardware risks; this addon does not change them.

## Sound

- MAX98357A BCLK: GP11; LRC/WS: GP12; DIN: GP13; common GND.
- Amplifier VIN: regulated 5 V as specified for this module in the user's PDF.
  Its speaker outputs are bridge outputs: neither speaker terminal goes to GND.
  The PDF's USB/battery power-combining circuit is NOT endorsed by this release.
- 16-bit I2S at 16 kHz; all four Game Boy sound channels.
- Left/right mixed to mono, identical data in both I2S slots. One MAX98357A
  is a mono amplifier, including when two speakers are connected in series.
- Fixed digital volume: **50%**. No new menu, controls, or startup beep.
- One PIO state machine, two dynamically claimed DMA channels, core-0 DMA IRQ1.
- 4,500 bytes of additional static RAM, reserved before the original heap.
- Output is stopped before the original video-stop/menu/ROM-flash transitions.
- On underflow, output silence instead of replaying stale PCM. Never block the
  emulator waiting for an audio buffer. Audio generation runs even on skipped
  LCD frames and uses fractional sample counting at the Game Boy frame rate.

Audio synthesis adds CPU work. Unchanged clock settings do not imply unchanged
FPS. Sound fidelity is limited by the lightweight, frame-batched MiniGB APU;
this is not a claim of cycle-accurate audio or stutter-free hardware playback.

## Verification

- ASan/UBSan: buffer sizes, queue capacity and 32-bit index wrap, 50% mono mix,
  power/reset behavior, tone generation, random register writes.
- Zelda, Aladdin, Pac-Man GB and Pokemon Yellow: 3,600 frames twice per ROM;
  no sanitizer errors, nonzero PCM, identical audio with video frames skipped.
- Unicorn executes the actual patched ARM register handlers and addon: stack
  and ABI preservation, non-audio memory paths, frame/render passthrough,
  I2S divider, underflow silence, stop and restart without DMA resource leaks.
- Independent instruction model validates assembled PIO bit order, 16-bit slots,
  the one-bit I2S delay, and 32 BCLK / 64 PIO cycles per stereo sample frame.
- The actual patched ARM emulator also boots the supplied Zelda and Aladdin ROMs
  and advances 120 frames each with nonzero generated PCM; this test does not use a recompiled
  substitute emulator core.
- Hardware APIs are mocked in ARM tests; physical speaker output and FPS still
  require testing on the user's console. No automatic flashing was performed.

## Rebuild

Requires the existing local Pico SDK 2.3.1 configuration in `firmware/build`,
ARM GCC 14.3.1 in `/tmp/arm-gnu`, Ninja, and pioasm. The build script reads SDK
include paths from Ninja, but does not rebuild or modify the original launcher.
Recovered imports are checked in as `audio-addon/base-symbols.ld` so no old ELF
or unavailable source snapshot is needed.

From the project root:

```sh
/Library/Developer/CommandLineTools/usr/bin/python3 firmware/tools/build_audio_addon.py firmware/audio-addon/base-v0_9-B-200mhz-lcd50-sd12.uf2
/Library/Developer/CommandLineTools/usr/bin/python3 firmware/tools/uf2_audio_patch.py firmware/audio-addon/base-v0_9-B-200mhz-lcd50-sd12.uf2 firmware/build-audio-addon firmware/releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-audio50.uf2
```

The linker may report that it forces branches to absolute imports into Thumb
mode. These are the recovered RP2040 SDK entry points; their branch destinations
and audio-hook ABI are tested independently. No ROM is bundled or modified.

Flash via BOOTSEL and copy the `audio50.uf2` file to RPI-RP2, as with the previous
firmware. Keep the original UF2 for rollback. Do not disconnect during the copy.
