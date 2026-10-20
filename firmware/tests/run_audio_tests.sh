#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
scarlet_cc=/Library/Developer/CommandLineTools/usr/bin/clang
scarlet_flags=(-std=c11 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all
 -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk -Ifirmware/include
 -Ifirmware/vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu -Ifirmware/vendor/Peanut-GB-CGB)
scarlet_apu=firmware/vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu/minigb_apu.c
"$scarlet_cc" "${scarlet_flags[@]}" firmware/tests/test_audio.c "$scarlet_apu" -o firmware/build-audio-addon/test-audio
firmware/build-audio-addon/test-audio
"$scarlet_cc" "${scarlet_flags[@]}" -DENABLE_SOUND=1 firmware/tests/test_audio_roms.c firmware/src/emulator.c "$scarlet_apu" -o firmware/build-audio-addon/test-audio-roms
firmware/build-audio-addon/test-audio-roms "$@"
