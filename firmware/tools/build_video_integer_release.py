#!/usr/bin/env python3
"""Exact 2x nearest-neighbour variant of the user-tested VIDEO16 UF2. No flash."""
from pathlib import Path
import hashlib, json, struct
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'releases/scarletpico-v2_2_2-video16-TEST.uf2'
EXPECTED='5137a17385011e5997287db167d46d5a82c1ca36e705bad970f265b07eb7e81a'
RELEASE=ROOT/'releases/scarletpico-v2_2_2-video16-2X-TEST.uf2'
OUT=ROOT/'build-video-integer-addon'

def main():
 raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 data=bytearray()
 for off in range(0,len(raw),512):
  block=raw[off:off+512]
  assert struct.unpack_from('<8I',block)==(0xa324655,0x9e5d5157,0x2000,0x10000000+off//2,256,off//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',block,508)[0]==0xab16f30
  data.extend(block[32:288])
 original=bytes(data);changes=[]
 # DISPLAY_LARGE=4 is an existing exact 2x path, NOT a different core
 # resolution. Include pause/resume and the honest serial size description.
 for address,target,reason in [
  (0x10007fa2,0x10008af0,'Game launch selects exact 2x'),
  (0x1003439a,0x10008af0,'Pause/state resume retains exact 2x'),
  (0x10008334,0x10001560,'PERF reports actual 320x288 mode')]:
  pos=address-0x10000000
  assert data[pos:pos+6]==bytes.fromhex('0520')+bl(address+2,target),hex(address)
  data[pos:pos+2]=bytes.fromhex('0420')
  changes.append(dict(address=hex(address),before='0520',after='0420',purpose=reason))
 changed={i for i,(a,b) in enumerate(zip(original,data)) if a!=b}
 assert changed=={int(c['address'],16)-0x10000000 for c in changes}
 assert data[0x23f8:0x7164]==original[0x23f8:0x7164], 'Core altered'
 result=bytearray(raw)
 for i in range(0,len(data),256):result[i*2+32:i*2+288]=data[i:i+256]
 OUT.mkdir(exist_ok=True);(OUT/'patched.bin').write_bytes(data)
 RELEASE.write_bytes(result)
 report=dict(version='2.2.2-video16-2x-test',source_sha256=EXPECTED,
  output_sha256=hashlib.sha256(result).hexdigest(),changes=changes,
  additional_flash_bytes=0,additional_ram_bytes=0,changed_payload_bytes=len(changed),
  native_size=[160,144],output_size=[320,288],offset=[80,16],
  pixels_per_full_update=92160,bytes_per_full_update=184320,
  reduction_from_fit_height_percent=(1-92160/113920)*100,
  original_video16_driver_audio_menu_clocks_preserved=True,
  physical_fps_not_yet_measured=True)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
