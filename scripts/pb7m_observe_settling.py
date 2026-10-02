"""Independent post-cancel views after explicitly reviewed native recovery.

No camera events or calibration authority are created. Recovery can raise the
same exact window and resume its visible pause menu, as ordinary Review does.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import threading
import time
from smb3_agent.camera_practice import activate_practice,resume_practice,calibration_from,native_hid_receipt,candidate_identity
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver
p=argparse.ArgumentParser();p.add_argument('--seal',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args();a.root.mkdir(parents=True,exist_ok=False)
s=json.loads(a.seal.read_text());cal=calibration_from(s['calibration']);r={'class':'post_cancel_recovery_observation_only','candidate':candidate_identity(),'binding':asdict(cal.binding),'camera_events_emitted':False,'began_at':time.monotonic()}
try:
 host=activate_practice(cal.binding);resume_practice(host,cal.binding,a.root,threading.Event());o=MinecraftCameraObserver(host,cal.environment,cal.calibration_id,a.root/'frames');first=o.observe(execution=True);time.sleep(.2);last=o.observe(execution=True);r['views']=[asdict(first),asdict(last)];r['native_neutral']=native_hid_receipt();r['residual']=[(last.heading-first.heading+540)%360-180,last.pitch-first.pitch];r['settled']=max(abs(x) for x in r['residual'])<=.1 and r['native_neutral']['confirmed']
except Exception as exc:r.update(error=str(exc),settled=False)
(a.root/'attempt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'settled':r['settled'],'error':r.get('error'),'residual':r.get('residual'),'path':str(a.root/'attempt.json')}))
if not r['settled']:raise SystemExit(1)
