#!/usr/bin/env python3
"""Package verified PACED + two exact rollback images, never flash."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'releases/2026-09-28-video-paced-test'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    new=ROOT/'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2'
    old=ROOT/'releases/scarletpico-v2_2_2-video16-SHADOW-TEST.uf2'
    older=ROOT/'releases/scarletpico-v2_2_2-video16-TEST.uf2'
    meta=json.loads(new.with_suffix('.json').read_text())
    assert digest(new)==meta['output_sha256'] and digest(old)==meta['source_sha256']
    assert digest(older)=='5137a17385011e5997287db167d46d5a82c1ca36e705bad970f265b07eb7e81a'
    checks=[('test-results.txt','PASS real audio enqueue wrapper:'),
            ('feature-regression.txt','PASS PACED + real feature pause/resume:'),
            ('video-regression.txt','PASS actual worker:')]
    for name,marker in checks:
        text=(ROOT/'build-video-pace-addon'/name).read_text()
        assert marker in text and text.rstrip().endswith('FIRMWARE_SHA256 '+digest(new)),name
    heap=(ROOT/'build-video-pace-addon/heap-regression.txt').read_text()
    assert 'PASS real pinned malloc/free:' in heap
    assert heap.rstrip().endswith('IMAGE_SHA256 '+digest(ROOT/'build-video-pace-addon/patched.bin'))
    pairs=[(old,'01-SHADOW-ROLLBACK.uf2'),(new,'02-FULL-HEIGHT-PACED-TEST.uf2'),
           (older,'03-VIDEO16-23FPS-ROLLBACK.uf2'),(new.with_suffix('.json'),'METADATA.json'),
           (ROOT/'VIDEO-PACE-TEST.md','README-RU.md')]
    for source,dest in [('test-results.txt','PACE-TESTS.txt'),('feature-regression.txt','FEATURE-TESTS.txt'),
                        ('video-regression.txt','VIDEO-TESTS.txt'),('heap-regression.txt','HEAP-TESTS.txt')]:
        pairs.append((ROOT/'build-video-pace-addon'/source,dest))
    BUNDLE.mkdir(exist_ok=True)
    for source,name in pairs:
        dest=BUNDLE/name
        if dest.exists():assert digest(dest)==digest(source),f'Refusing to overwrite {dest}'
        else:shutil.copyfile(source,dest)
    (BUNDLE/'SHA256SUMS.txt').write_text(''.join(f'{digest(BUNDLE/name)}  {name}\n' for _,name in pairs))
    print(BUNDLE)
if __name__=='__main__':main()
