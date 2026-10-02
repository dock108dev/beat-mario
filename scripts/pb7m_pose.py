"""Separate exploratory pose preparation; never a qualification goal result."""
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4
from smb3_agent.camera_practice import (EVIDENCE, activate_practice, binding_from,
    calibration_from, environment, resume_practice)
from smb3_agent.camera_native_input import CameraMotionGuard
from smb3_agent.feedback_contracts import RelativePointerAction, heading_delta
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver
import threading

p=argparse.ArgumentParser();p.add_argument('--session',default='session-1');p.add_argument('--heading',type=float,required=True);p.add_argument('--pitch',type=float,required=True)
a=p.parse_args()
if not -180<=a.heading<=180 or not -90<=a.pitch<=90:raise ValueError('Pose outside limits')
r=[r for r in json.loads((EVIDENCE/'approved-sessions.json').read_text()) if r['id']==a.session]
if len(r)!=1:raise ValueError('No approved practice receipt')
cal=calibration_from(r[0]['calibration']);binding=binding_from(r[0]['calibration']['binding'])
if binding.process_id==74438 or cal.environment!=environment():raise ValueError('Preparation binding changed')
root=EVIDENCE/'pose-preparation'/uuid4().hex;root.mkdir(parents=True)
host=activate_practice(binding);resume_practice(host,binding,root,threading.Event())
obs=MinecraftCameraObserver(host,cal.environment,cal.calibration_id,root/'frames')
record={'class':'exploratory_pose_preparation_only','target':[a.heading,a.pitch],'steps':[]}
guard=CameraMotionGuard(binding,1,cal.environment.controls_id,root)
try:
 for index in range(32):
  before=obs.observe(execution=True);before.require(before.grounded_at,.8,.1)
  error=(heading_delta(a.heading,before.heading),a.pitch-before.pitch)
  if max(map(abs,error))<=.1:break
  axis=0 if abs(error[0])>=abs(error[1]) else 1
  units=max(1,min(100,round(abs(error[axis])/.15)))*(1 if error[axis]>0 else -1)
  now=time.monotonic();act=RelativePointerAction(units if axis==0 else 0,units if axis==1 else 0,120,now,now+.12,1,before.frame)
  step={'before':asdict(before),'action':asdict(act)};record['steps'].append(step)
  receipt=guard.pulse(act);step['delivery']=receipt;time.sleep(.14);after=obs.observe(execution=True);step['after']=asdict(after);after.require(after.grounded_at,.8,.1)
  measured=(heading_delta(after.heading,before.heading),after.pitch-before.pitch)
  expected=(act.dx*.15,act.dy*.15)
  if max(abs(x-y) for x,y in zip(measured,expected))>.2:raise ValueError('Unexpected preparation response')
 else:raise ValueError('Finite pose preparation budget exhausted')
 record['error']=None
except Exception as exc:
 record['error']=str(exc)
finally:
 record['release']=guard.cancel();first=obs.observe(execution=True);time.sleep(.2);last=obs.observe(execution=True)
 record['settles']=[asdict(first),asdict(last)];(root/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({'evidence':str(root/'attempt.json'),'error':record.get('error'),'final':[last.heading,last.pitch]}))
 if record.get('error'):raise SystemExit(1)
