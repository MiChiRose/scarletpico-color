#!/usr/bin/env python3
"""Package exact verified fast-codec image and its untouched rollback."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-shadow-fast-addon'
BUNDLE=ROOT/'releases/2026-09-28-shadow-fast-test'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 new=ROOT/'releases/scarletpico-v2_2_2-SHADOW-FAST-TEST.uf2'
 old=ROOT/'releases/scarletpico-v2_2_2-PAUSE-SETTINGS-TEST.uf2'
 meta=json.loads(new.with_suffix('.json').read_text())
 assert digest(new)==meta['output_sha256'] and digest(old)==meta['source_sha256']
 markers={'codec':['PASS differential codec:'],
          'ui':['PASS feature tests:','PASS live settings:','PASS new five-row pause navigation:'],
          'pace':['PASS real audio enqueue wrapper:'],
          'video':['PASS actual worker:']}
 for name,required in markers.items():
  text=(BUILD/(name+'-regression.txt')).read_text()
  assert all(marker in text for marker in required),name
  assert text.rstrip().endswith('FIRMWARE_SHA256 '+digest(new)),name
 heap=(BUILD/'heap-regression.txt').read_text()
 assert 'PASS real pinned malloc/free:' in heap
 assert heap.rstrip().endswith('IMAGE_SHA256 '+digest(BUILD/'patched.bin'))
 bench=json.loads((BUILD/'codec-benchmark.json').read_text())
 assert bench['output_sha256']==digest(new)
 pairs=[(old,'01-PAUSE-SETTINGS-ROLLBACK.uf2'),(new,'02-SHADOW-FAST-TEST.uf2'),
        (new.with_suffix('.json'),'METADATA.json'),(ROOT/'SHADOW-FAST-TEST.md','README-RU.md'),
        (BUILD/'codec-benchmark.json','CODEC-BENCHMARK.json')]
 for name in ['codec','ui','pace','video','heap']:
  pairs.append((BUILD/(name+'-regression.txt'),name.upper()+'-TESTS.txt'))
 BUNDLE.mkdir(exist_ok=True)
 for source,name in pairs:
  dest=BUNDLE/name
  if dest.exists():assert digest(dest)==digest(source),'Refusing to overwrite '+str(dest)
  else:shutil.copyfile(source,dest)
 (BUNDLE/'SHA256SUMS.txt').write_text(''.join(f'{digest(BUNDLE/name)}  {name}\n' for _,name in pairs))
 print(BUNDLE)
if __name__=='__main__':main()
