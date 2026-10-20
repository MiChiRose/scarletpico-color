#!/usr/bin/env python3
"""Package only the selected full-height experiment and exact 23-FPS rollback."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'releases/2026-09-28-video-shadow-test'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 new=ROOT/'releases/scarletpico-v2_2_2-video16-SHADOW-TEST.uf2'
 old=ROOT/'releases/scarletpico-v2_2_2-video16-TEST.uf2'
 meta=json.loads(new.with_suffix('.json').read_text())
 assert digest(new)==meta['output_sha256'] and digest(old)==meta['source_sha256']
 for log,marker in [('test-results.txt','PASS actual worker:'),('feature-regression.txt','PASS feature tests:')]:
  text=(ROOT/'build-video-shadow-addon'/log).read_text()
  assert marker in text and text.rstrip().endswith('FIRMWARE_SHA256 '+meta['output_sha256'])
 heap=(ROOT/'build-video-shadow-addon/heap-regression.txt').read_text()
 assert 'PASS real pinned malloc/free:' in heap
 assert heap.rstrip().endswith('IMAGE_SHA256 '+digest(ROOT/'build-video-shadow-addon/patched.bin'))
 pairs=[(old,'01-VIDEO16-23FPS-ROLLBACK.uf2'),(new,'02-FULL-HEIGHT-SHADOW-TEST.uf2'),
  (new.with_suffix('.json'),'METADATA.json'),(ROOT/'VIDEO-SHADOW-TEST.md','README-RU.md'),
  (ROOT/'build-video-shadow-addon/test-results.txt','VIDEO-TESTS.txt'),
  (ROOT/'build-video-shadow-addon/feature-regression.txt','FEATURE-TESTS.txt'),
  (ROOT/'build-video-shadow-addon/heap-regression.txt','HEAP-TESTS.txt')]
 BUNDLE.mkdir(exist_ok=True)
 for source,name in pairs:
  target=BUNDLE/name
  if target.exists():assert digest(target)==digest(source),f'Refusing to overwrite {target}'
  else:shutil.copyfile(source,target)
 (BUNDLE/'SHA256SUMS.txt').write_text(''.join(f'{digest(BUNDLE/name)}  {name}\n' for _,name in pairs))
 print(BUNDLE)
if __name__=='__main__':main()
