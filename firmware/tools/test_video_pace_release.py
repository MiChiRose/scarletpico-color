#!/usr/bin/env python3
"""Run and retain regression logs for the exact built image. No device access."""
from pathlib import Path
import os, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-video-pace-addon'
def main():
    cases={
        'pace':('test_video_pace_arm.py','test-results.txt',{}),
        'features':('test_video_pace_features_arm.py','feature-regression.txt',{}),
        'video':('test_video_shadow_arm.py','video-regression.txt',{
            'SCARLET_SHADOW_IMAGE':str(OUT/'patched.bin'),
            'SCARLET_SHADOW_UF2':str(ROOT/'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2')}),
        'heap':('test_video_heap_arm.py','heap-regression.txt',{
            'SCARLET_HEAP_IMAGE':str(OUT/'patched.bin')})}
    for name in sys.argv[1:] or cases:
        script,log,extra=cases[name]
        env=os.environ.copy();env.update(extra)
        with (OUT/log).open('w') as output:
            process=subprocess.Popen([sys.executable,'-u',str(ROOT/'tests'/script)],
                                     env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in process.stdout:
                print(line,end='',flush=True);output.write(line);output.flush()
            code=process.wait()
        if code:raise SystemExit(code)
if __name__=='__main__':main()
