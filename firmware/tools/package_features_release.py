#!/usr/bin/env python3
"""Package only verified local build artifacts; never flash or touch a card."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'releases/2026-09-28-features-v2_2_1'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 base=ROOT/'releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1-fastload.uf2'
 previous=ROOT/'releases/scarletpico-features-v2_2-experimental.uf2'
 assert digest(previous)=='8370b36d2678cced8e15c38c3c612126dee928e0047e5829991b94f1a9282e78'
 new=ROOT/'releases/scarletpico-features-v2_2_1-experimental.uf2'
 meta=json.loads(new.with_suffix('.json').read_text())
 assert digest(base)==meta['source_sha256'] and digest(new)==meta['output_sha256']
 log=ROOT/'build-features-v2_2_1-addon/test-results.txt'
 assert 'PASS feature tests:' in log.read_text(),'Complete ARM test run required'
 assert 'PASS boot:' in log.read_text() and 'PASS chime:' in log.read_text(),'Boot and audio checks required'
 assert 'FIRMWARE_SHA256 '+meta['output_sha256'] in log.read_text(),'Tests must match packaged UF2'
 BUNDLE.mkdir(exist_ok=True)
 pairs=[(previous,'01-features-v2_2-ROLLBACK.uf2'),(new,'02-features-v2_2_1-EXPERIMENTAL.uf2'),
        (new.with_suffix('.json'),'02-features-v2_2_1-EXPERIMENTAL.json'),
        (ROOT/'FEATURES-V2_2_1.md','README-RU.md'),(ROOT/'FEATURES-V2_2.md','FEATURES-V2_2.md'),
        (ROOT/'FEATURES-V2_1.md','FEATURES-V2_1.md'),
        (ROOT/'FEATURES-V2.md','FEATURES-V2.md'),(log,'TEST-RESULTS.txt'),
        (ROOT/'build-features-v2_2_1-addon/previews/boot-preview.gif','BOOT-PREVIEW.gif'),
        (ROOT/'build-features-v2_2_1-addon/previews/boot-chime-50.wav','BOOT-CHIME-50.wav')]
 for source,name in pairs:
  target=BUNDLE/name
  if 'ROLLBACK' in name and target.exists():assert digest(target)==digest(source)
  else:shutil.copyfile(source,target)
 sums=''.join(f'{digest(BUNDLE/name)}  {name}\n' for _,name in pairs)
 (BUNDLE/'SHA256SUMS.txt').write_text(sums)
 print(BUNDLE)
if __name__=='__main__':main()
