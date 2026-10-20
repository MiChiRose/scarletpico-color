#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
task_cc=${SCARLET_TEST_CC:-/Library/Developer/CommandLineTools/usr/bin/clang}
task_python=${SCARLET_TEST_PYTHON:-python3}
task_out=firmware/build-rp2350-source
task_source=firmware/imported/scarletpico-rp2350-source
mkdir -p "$task_out/previews"
task_flags=(-std=c11 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all
 -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)
"$task_cc" "${task_flags[@]}" -I"$task_source/third_party/peanut" -I"$task_source" "$task_source/test_host.c" -o "$task_out/test-core"
"$task_out/test-core"
"$task_cc" "${task_flags[@]}" -Ifirmware/tests/stubs -I"$task_source/third_party/sd/ff15/source" \
 firmware/tests/test_rp2350_states.c "$task_source/console_state.c" -o "$task_out/test-states"
"$task_out/test-states"
"$task_cc" "${task_flags[@]}" -I"$task_source/third_party/sd/ff15/source" \
 firmware/tests/test_partition_mount.c "$task_source/partition_map.c" \
 "$task_source/third_party/sd/ff15/source/ff.c" "$task_source/third_party/sd/ff15/source/ffsystem.c" \
 "$task_source/third_party/sd/ff15/source/ffunicode.c" -o "$task_out/test-partition"
"$task_out/test-partition"
"$task_cc" "${task_flags[@]}" -DSCARLET_NATIVE_SOURCE=1 firmware/tests/test_ui.c firmware/ui-addon/ui.c -o "$task_out/test-ui"
"$task_out/test-ui" "$task_out/previews"
"$task_python" firmware/tests/test_rp2350_menu_arm.py
if (( $# )); then
 task_apu=firmware/vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu
 "$task_cc" "${task_flags[@]}" -I"$task_source/third_party/peanut" -I"$task_apu" \
  firmware/tests/test_rp2350_roms.c "$task_apu/minigb_apu.c" -o "$task_out/test-roms"
 "$task_out/test-roms" "$@"
fi
