#!/usr/bin/env python3
"""Keep the tested rollback, sound-only build and DMA experiment distinct."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'releases/2026-09-28-video-dma-test'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 new=ROOT/'releases/scarletpico-v2_2_1-video-dma-TEST.uf2'
 meta=json.loads(new.with_suffix('.json').read_text())
 assert digest(new)==meta['output_sha256']
 chime=ROOT/'releases/scarletpico-features-v2_2_1-experimental.uf2'
 old=ROOT/'releases/scarletpico-features-v2_2-experimental.uf2'
 assert digest(chime)==meta['source_sha256']
 assert digest(old)=='8370b36d2678cced8e15c38c3c612126dee928e0047e5829991b94f1a9282e78'
 for file,marker in [('test-results.txt','PASS original renderer + new transport:'),('feature-regression.txt','PASS feature tests:')]:
  log=(ROOT/'build-video-dma-addon'/file).read_text()
  assert marker in log and 'FIRMWARE_SHA256 '+meta['output_sha256'] in log
 pairs=[(old,'01-v2_2-USER-TESTED-ROLLBACK.uf2'),(new,'02-video-dma-TEST.uf2'),
        (chime,'03-v2_2_1-CHIME-ONLY.uf2'),(new.with_suffix('.json'),'DMA-METADATA.json'),
        (ROOT/'VIDEO-DMA-TEST.md','README-RU.md'),
        (ROOT/'FEATURES-V2_2_1.md','CHIME-ONLY.md'),
        (ROOT/'FEATURES-V2_2.md','FEATURES-V2_2.md'),
        (ROOT/'FEATURES-V2_1.md','FEATURES-V2_1.md'),
        (ROOT/'FEATURES-V2.md','FEATURES-V2.md'),
        (ROOT/'build-video-dma-addon/test-results.txt','DMA-TESTS.txt'),
        (ROOT/'build-video-dma-addon/feature-regression.txt','FEATURE-REGRESSION.txt'),
        (ROOT/'build-features-v2_2_1-addon/previews/boot-chime-50.wav','BOOT-CHIME-50.wav')]
 BUNDLE.mkdir(exist_ok=True)
 for src,name in pairs:shutil.copyfile(src,BUNDLE/name)
 (BUNDLE/'SHA256SUMS.txt').write_text(''.join(f'{digest(BUNDLE/name)}  {name}\n' for _,name in pairs))
 print(BUNDLE)
if __name__=='__main__':main()
