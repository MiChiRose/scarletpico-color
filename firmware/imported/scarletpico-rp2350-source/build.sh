#!/bin/bash
set -euo pipefail
task_source_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
: "${PICO_SDK_PATH:?Set PICO_SDK_PATH to Pico SDK 2.3.0 or compatible}"
profile="${1:-B}"
case "$profile" in
  A) cpu=200000; lcd=50000000; scale=3 ;;
  B) cpu=200000; lcd=100000000; scale=2 ;;
  C) cpu=240000; lcd=120000000; scale=2 ;;
  D) cpu=200000; lcd=100000000; scale=3 ;;
  *) printf '%s\n' 'Usage: build.sh A|B|C|D'; exit 2 ;;
esac
cmake -S "$task_source_dir" -B "$task_source_dir/build-$profile" \
  -DPICO_SDK_PATH="$PICO_SDK_PATH" -DCMAKE_BUILD_TYPE=Release \
  -DSCARLET_CPU_KHZ="$cpu" -DSCARLET_LCD_HZ="$lcd" -DSCARLET_SCALE="$scale"
cmake --build "$task_source_dir/build-$profile" --parallel 4
printf '\nUF2: %s/build-%s/scarlet2350.uf2\n' "$task_source_dir" "$profile"
