#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

scarlet_cc="${SCARLET_HOST_CC:-cc}"
scarlet_flags=(-std=c11 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all)
if [[ -x /Library/Developer/CommandLineTools/usr/bin/clang && -z "${SCARLET_HOST_CC:-}" ]]; then
    scarlet_cc=/Library/Developer/CommandLineTools/usr/bin/clang
    scarlet_flags+=(-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)
fi
scarlet_tmp=$(mktemp -d "${TMPDIR:-/tmp}/scarletpico-tests.XXXXXX")
fatfs_flags=(-Ifirmware/vendor/pico-fatfs-sd/src/include -Ifirmware/vendor/pico-fatfs-sd/lib/fatfs/source)

"$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror \
    -Ifirmware/vendor/pico-fatfs-sd/src/sd_driver "${fatfs_flags[@]}" \
    firmware/tests/test_sdsc.c -o "$scarlet_tmp/sdsc"
"$scarlet_tmp/sdsc"

"$scarlet_cc" "${scarlet_flags[@]}" "${fatfs_flags[@]}" \
    firmware/tests/test_partition_mount.c firmware/src/partition_map.c \
    firmware/vendor/pico-fatfs-sd/lib/fatfs/source/ff.c \
    firmware/vendor/pico-fatfs-sd/lib/fatfs/source/ffsystem.c \
    firmware/vendor/pico-fatfs-sd/lib/fatfs/source/ffunicode.c \
    -o "$scarlet_tmp/partition"
"$scarlet_tmp/partition"

"$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror \
    -Ifirmware/tests/stubs -Ifirmware/include \
    firmware/src/display_st7796.c firmware/tests/test_display.c -o "$scarlet_tmp/display"
"$scarlet_tmp/display"

"$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror -pthread \
    -Ifirmware/tests/stubs -Ifirmware/include \
    firmware/tests/test_video_worker.c -o "$scarlet_tmp/video-worker"
"$scarlet_tmp/video-worker"

"$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror \
    -Ifirmware/tests/stubs -Ifirmware/include \
    firmware/src/freeze_guard.c firmware/tests/test_freeze_guard.c -o "$scarlet_tmp/freeze-guard"
"$scarlet_tmp/freeze-guard"

"$scarlet_cc" "${scarlet_flags[@]}" -Ifirmware/include -Ifirmware/vendor/Peanut-GB-CGB \
    firmware/src/emulator.c firmware/tests/test_emulator_timeout.c -o "$scarlet_tmp/emulator-timeout"
"$scarlet_tmp/emulator-timeout"

"$scarlet_cc" "${scarlet_flags[@]}" -Ifirmware/include -Ifirmware/vendor/Peanut-GB-CGB \
    firmware/tests/test_emulator_core.c -o "$scarlet_tmp/emulator-core"
"$scarlet_tmp/emulator-core"

"$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror \
    -Ifirmware/tests/stubs -Ifirmware/include "${fatfs_flags[@]}" \
    firmware/tests/test_launcher.c -o "$scarlet_tmp/launcher"
"$scarlet_tmp/launcher"
"$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror -DGAME_CLOCK_KHZ=200000u \
    -Ifirmware/tests/stubs -Ifirmware/include "${fatfs_flags[@]}" \
    firmware/tests/test_launcher.c -o "$scarlet_tmp/launcher-200"
"$scarlet_tmp/launcher-200"

aladdin_rom='roms/Aladdin (U) [C][!].gbc'
zelda_rom="roms/Legend of Zelda, The - Link's Awakening (U) (V1.2) [!].gb"
if [[ -f "$aladdin_rom" && -f "$zelda_rom" ]]; then
    "$scarlet_cc" "${scarlet_flags[@]}" -Wall -Wextra -Werror \
        -Ifirmware/include "${fatfs_flags[@]}" \
        firmware/src/game_library.c firmware/tests/test_game_library.c -o "$scarlet_tmp/library"
    "$scarlet_tmp/library"
    "$scarlet_cc" "${scarlet_flags[@]}" -Ifirmware/include -Ifirmware/vendor/Peanut-GB-CGB \
        firmware/src/emulator.c firmware/tests/test_emulator_roms.c -o "$scarlet_tmp/emulator"
    "$scarlet_tmp/emulator" "$aladdin_rom" "$scarlet_tmp/aladdin"
    "$scarlet_tmp/emulator" "$zelda_rom" "$scarlet_tmp/zelda"
else
    echo 'SKIP: real-ROM tests require the locally supplied Aladdin and Zelda files.'
fi
# Optional local ROMs are supplied explicitly; never download or package games.
if (( $# )); then
    "$scarlet_cc" "${scarlet_flags[@]}" -Ifirmware/include -Ifirmware/vendor/Peanut-GB-CGB \
        firmware/src/emulator.c firmware/tests/test_emulator_roms.c -o "$scarlet_tmp/emulator"
    "$scarlet_cc" "${scarlet_flags[@]}" -Ifirmware/tests/stubs -Ifirmware/include \
        -Ifirmware/vendor/Peanut-GB-CGB firmware/src/emulator.c firmware/src/display_st7796.c \
        firmware/tests/test_video_roms.c -o "$scarlet_tmp/video-roms"
    index=0
    for rom in "$@"; do
        index=$((index + 1))
        "$scarlet_tmp/emulator" "$rom" "$scarlet_tmp/extra-$index"
        "$scarlet_tmp/video-roms" "$rom" "$scarlet_tmp/video-$index"
    done
fi
echo "Test binaries and frame captures: $scarlet_tmp"
