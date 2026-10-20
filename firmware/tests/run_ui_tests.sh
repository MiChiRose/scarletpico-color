#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
out=firmware/build-ui-addon
mkdir -p "$out/previews"
/Library/Developer/CommandLineTools/usr/bin/clang -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk -std=c11 -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -Wall -Wextra -Werror firmware/tests/test_ui.c firmware/ui-addon/ui.c -o "$out/test-ui"
"$out/test-ui" "$out/previews"
for ppm in "$out"/previews/*.ppm; do
 /usr/bin/sips -s format png "$ppm" --out "${ppm%.ppm}.png" >/dev/null
done
