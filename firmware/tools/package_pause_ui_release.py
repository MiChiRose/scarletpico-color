#!/usr/bin/env python3
"""Package only fully tested, hash-matching UF2 files. Never access a device."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build-pause-ui-addon'
BUNDLE=ROOT/'releases/2026-09-28-pause-settings-test'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    new=ROOT/'releases/scarletpico-v2_2_2-PAUSE-SETTINGS-TEST.uf2'
    old=ROOT/'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2'
    meta=json.loads(new.with_suffix('.json').read_text())
    assert digest(new)==meta['output_sha256'] and digest(old)==meta['source_sha256']
    for log,markers in {
        'ui-regression.txt':['PASS feature tests:', 'PASS live settings:',
                             'PASS real RU in-game settings:', 'PASS new five-row pause navigation:'],
        'pace-regression.txt':['PASS real audio enqueue wrapper:'],
        'video-regression.txt':['PASS actual worker:']}.items():
        text=(BUILD/log).read_text()
        assert all(marker in text for marker in markers),log
        assert text.rstrip().endswith('FIRMWARE_SHA256 '+digest(new)),log
    heap=(BUILD/'heap-regression.txt').read_text()
    assert 'PASS real pinned malloc/free:' in heap
    assert heap.rstrip().endswith('IMAGE_SHA256 '+digest(BUILD/'patched.bin'))
    pairs=[(old,'01-PACED-ROLLBACK.uf2'),(new,'02-PAUSE-SETTINGS-TEST.uf2'),
           (new.with_suffix('.json'),'METADATA.json'),(ROOT/'PAUSE-SETTINGS-TEST.md','README-RU.md')]
    for name in ['ui','pace','video','heap']:
        pairs.append((BUILD/(name+'-regression.txt'),name.upper()+'-TESTS.txt'))
    for name in ['pause-settings-ru','pause-settings-en','in-game-settings-ru','bottom-fps']:
        pairs.append((BUILD/'previews'/(name+'.png'),name+'.png'))
    BUNDLE.mkdir(exist_ok=True)
    for source,name in pairs:
        dest=BUNDLE/name
        if dest.exists():assert digest(dest)==digest(source),'Refusing to overwrite '+str(dest)
        else:shutil.copyfile(source,dest)
    (BUNDLE/'SHA256SUMS.txt').write_text(''.join(f'{digest(BUNDLE/name)}  {name}\n' for _,name in pairs))
    print(BUNDLE)
if __name__=='__main__':main()
