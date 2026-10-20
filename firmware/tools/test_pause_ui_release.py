#!/usr/bin/env python3
"""Retain regression logs for the precise UI test UF2. No physical device I/O."""
from pathlib import Path
import os, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-pause-ui-addon'
UF2=str(ROOT/'releases/scarletpico-v2_2_2-PAUSE-SETTINGS-TEST.uf2')
IMAGE=str(OUT/'patched.bin')
def main():
    cases={
        'ui':('test_pause_ui_arm.py','ui-regression.txt',{}),
        'pace':('test_video_pace_arm.py','pace-regression.txt',{
            'SCARLET_PACE_IMAGE':IMAGE,'SCARLET_PACE_UF2':UF2}),
        'video':('test_video_shadow_arm.py','video-regression.txt',{
            'SCARLET_SHADOW_IMAGE':IMAGE,'SCARLET_SHADOW_UF2':UF2}),
        'heap':('test_video_heap_arm.py','heap-regression.txt',{'SCARLET_HEAP_IMAGE':IMAGE})}
    for name in sys.argv[1:] or cases:
        script,log,extra=cases[name]
        env=os.environ.copy();env.update(extra)
        with (OUT/log).open('w') as output:
            process=subprocess.Popen([sys.executable,'-u',str(ROOT/'tests'/script)],env=env,
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in process.stdout:
                print(line,end='',flush=True);output.write(line);output.flush()
            if process.wait():raise SystemExit(process.returncode)
if __name__=='__main__':main()
