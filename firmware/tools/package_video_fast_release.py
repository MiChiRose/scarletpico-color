#!/usr/bin/env python3
"""Package verified VIDEO16, chime-only and exact rollbacks; never flash."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'releases/2026-09-28-video16-test'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    new = ROOT / 'releases/scarletpico-v2_2_2-video16-TEST.uf2'
    meta = json.loads(new.with_suffix('.json').read_text())
    chime = ROOT / 'releases/scarletpico-features-v2_2_2-experimental.uf2'
    previous = ROOT / 'releases/scarletpico-v2_2_1-video-dma-TEST.uf2'
    old = ROOT / 'releases/scarletpico-features-v2_2-experimental.uf2'
    assert digest(new) == meta['output_sha256']
    assert digest(chime) == meta['source_sha256']
    assert digest(previous) == '0956e84d4d81afd65dc29d164e058a129e00cbf645bff73ea3d6746a643162a3'
    assert digest(old) == '8370b36d2678cced8e15c38c3c612126dee928e0047e5829991b94f1a9282e78'
    logs = [
        ('build-video-fast-addon/test-results.txt', 'PASS VIDEO16 fault handling:', digest(new)),
        ('build-video-fast-addon/feature-regression.txt', 'PASS feature tests:', digest(new)),
        ('build-features-v2_2_2-addon/test-results.txt', 'PASS feature tests:', digest(chime)),
    ]
    for name, marker, sha in logs:
        log = (ROOT / name).read_text()
        assert marker in log and 'FIRMWARE_SHA256 ' + sha in log
    pairs = [
        (previous, '01-previous-DMA8-ROLLBACK.uf2'),
        (new, '02-video16-TEST.uf2'),
        (chime, '03-v2_2_2-LONG-CHIME-ONLY.uf2'),
        (old, '04-v2_2-USER-TESTED-ROLLBACK.uf2'),
        (new.with_suffix('.json'), 'VIDEO16-METADATA.json'),
        (chime.with_suffix('.json'), 'CHIME-METADATA.json'),
        (ROOT / 'VIDEO16-TEST.md', 'README-RU.md'),
        (ROOT / 'FEATURES-V2_2_2.md', 'CHIME-ONLY.md'),
        (ROOT / 'FEATURES-V2_2.md', 'FEATURES-V2_2.md'),
        (ROOT / 'FEATURES-V2_1.md', 'FEATURES-V2_1.md'),
        (ROOT / 'FEATURES-V2.md', 'FEATURES-V2.md'),
        (ROOT / logs[0][0], 'VIDEO16-TESTS.txt'),
        (ROOT / logs[1][0], 'FEATURE-REGRESSION.txt'),
        (ROOT / logs[2][0], 'CHIME-TESTS.txt'),
        (ROOT / 'build-features-v2_2_2-addon/previews/boot-chime-50.wav', 'BOOT-CHIME-50.wav'),
    ]
    BUNDLE.mkdir(exist_ok=True)
    for source, name in pairs:
        target = BUNDLE / name
        if target.exists():
            assert digest(target) == digest(source), f'Refusing to replace {target}'
        else:
            shutil.copyfile(source, target)
    (BUNDLE / 'SHA256SUMS.txt').write_text(''.join(
        f'{digest(BUNDLE / name)}  {name}\n' for _, name in pairs))
    print(BUNDLE)


if __name__ == '__main__':
    main()
