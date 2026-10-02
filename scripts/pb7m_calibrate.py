"""Explicit engineering readiness and full repeated directional measurement."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import subprocess
import threading
import time
from uuid import uuid4

from smb3_agent.camera_native_input import CameraMotionGuard, settings_snapshot
from smb3_agent.camera_practice import activate_practice, resume_practice, environment, candidate_identity, native_hid_receipt
from smb3_agent.camera_readiness import acquire_readiness
from smb3_agent.feedback_contracts import WindowBinding, RelativePointerAction, CalibrationSample
from smb3_agent.feedback_policy import CameraCalibration
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver

p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--window',required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--id',required=True);a=p.parse_args()
a.root.mkdir(parents=True,exist_ok=False)
start=subprocess.check_output(['ps','-p',str(a.pid),'-o','lstart='],text=True).strip()
b=WindowBinding(a.pid,start,a.window,(329,223,854,508),(1708,1016));env=environment();cancel=threading.Event();holder=[None]
def stop(*_):
 cancel.set()
 if holder[0]:holder[0].cancel()
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
def publish(g):
 holder[0]=g
 if cancel.is_set():g.cancel();raise ValueError('canceled during preparation')
record={'class':'engineering_calibration_only','candidate':candidate_identity(),'environment':asdict(env),'settings':settings_snapshot(),'binding':asdict(b),'samples':[],'accepted':False}
try:
 host=activate_practice(b);resume_practice(host,b,a.root,cancel)
 observer=MinecraftCameraObserver(host,env,a.id,a.root/'frames')
 record['readiness']=acquire_readiness(observer,b,env.controls_id,1,cancel,a.root/'readiness',publish_guard=publish,neutral_receipt=native_hid_receipt,feedback_identity=(env.sha256,a.id))
 samples=[]
 for i,(dx,dy) in enumerate([(4,0),(12,0),(-4,0),(-12,0),(0,4),(0,12),(0,-4),(0,-12)]):
  root=a.root/'samples'/f'{i+1:02}-{uuid4().hex}';root.mkdir(parents=True)
  observer=MinecraftCameraObserver(host,env,a.id,root/'frames')
  g=CameraMotionGuard(b,1,env.controls_id,root);publish(g)
  row={'class':'directional_calibration_sample','index':i+1}
  try:
   before=observer.observe(execution=True);before.require(time.monotonic(),.8,.1)
   now=time.monotonic();act=RelativePointerAction(dx,dy,120,now,now+.12,1,before.frame);row.update(before=asdict(before),action=asdict(act))
   if cancel.is_set():raise ValueError('canceled before sample')
   row['delivery']=g.pulse(act)
   if cancel.wait(.14):raise ValueError('canceled after sample')
   after=observer.observe(execution=True);after.require(time.monotonic(),.8,.1);row['after']=asdict(after);row['timing']=observer.last_timing
   sample=CalibrationSample(act,before,after,row['delivery']['delivered_at'],str(root/'native-motion.jsonl'))
   row['response']=sample.response
   if max(abs(x-y) for x,y in zip(sample.response,(dx*.15,dy*.15)))>.3:raise ValueError('Contradictory calibration response; group stopped')
   samples.append(sample)
  except Exception as exc:
   row['error']=str(exc)
  finally:
   row['release']=g.cancel();row['canceled_at']=time.monotonic();row['native_neutral']=native_hid_receipt()
   try:
    first=observer.observe(execution=True);time.sleep(.2);last=observer.observe(execution=True);row['settling']=[asdict(first),asdict(last)]
    if abs(last.heading-first.heading)>.1 or abs(last.pitch-first.pitch)>.1 or not row['native_neutral']['confirmed']:raise ValueError('Calibration neutral settling failed')
   except Exception as exc:row['error']=row.get('error') or str(exc)
   (root/'attempt.json').write_text(json.dumps(row,indent=2)+'\n');record['samples'].append({'path':str(root/'attempt.json'),**row})
  if row.get('error'):raise ValueError(row['error'])
 cal=CameraCalibration(a.id,env,b,tuple(samples),(.15,)*4,.2,str(a.root/'batch.json'))
 record['accepted']=True;record['calibration']=asdict(cal);record['calibration_sha256']=cal.sha256
except Exception as exc:record['error']=str(exc)
finally:
 if holder[0]:holder[0].cancel()
 (a.root/'batch.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'path':str(a.root/'batch.json'),'accepted':record['accepted'],'samples':len(record['samples']),'error':record.get('error'),'calibration_sha256':record.get('calibration_sha256')}))
if not record['accepted']:raise SystemExit(1)
