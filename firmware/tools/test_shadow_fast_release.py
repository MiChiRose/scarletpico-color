#!/usr/bin/env python3
"""Regression logs for the exact shadow-fast UF2. No hardware access."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build-shadow-fast-addon'
UF2=str(ROOT/'releases/scarletpico-v2_2_2-SHADOW-FAST-TEST.uf2');IMAGE=str(OUT/'patched.bin')
def main():
 cases={
  'codec':('test_shadow_fast_codec_arm.py','codec-regression.txt',{}),
  'ui':('test_pause_ui_arm.py','ui-regression.txt',{'SCARLET_FEATURE_IMAGE':IMAGE,'SCARLET_FEATURE_UF2':UF2}),
  'pace':('test_video_pace_arm.py','pace-regression.txt',{'SCARLET_PACE_IMAGE':IMAGE,'SCARLET_PACE_UF2':UF2}),
  'video':('test_video_shadow_arm.py','video-regression.txt',{'SCARLET_SHADOW_IMAGE':IMAGE,'SCARLET_SHADOW_UF2':UF2}),
  'heap':('test_video_heap_arm.py','heap-regression.txt',{'SCARLET_HEAP_IMAGE':IMAGE})}
 for name in sys.argv[1:] or cases:
  script,log,extra=cases[name];env=os.environ.copy();env.update(extra)
  with (OUT/log).open('w') as output:
   process=subprocess.Popen([sys.executable,'-u',str(ROOT/'tests'/script)],env=env,
                            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   for line in process.stdout:print(line,end='',flush=True);output.write(line);output.flush()
   if process.wait():raise SystemExit(process.returncode)
if __name__=='__main__':main()
