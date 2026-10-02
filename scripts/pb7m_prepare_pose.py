"""Explicit pose preparation, excluded from qualification and goal budgets."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import threading
import time
from uuid import uuid4
from smb3_agent.camera_practice import activate_practice, resume_practice, calibration_from, native_hid_receipt, candidate_identity
from smb3_agent.camera_readiness import acquire_readiness
from smb3_agent.camera_native_input import CameraMotionGuard
from smb3_agent.feedback_contracts import RelativePointerAction, heading_delta
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver
p=argparse.ArgumentParser();p.add_argument('--seal',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--heading',type=float,required=True);p.add_argument('--pitch',type=float,required=True);a=p.parse_args()
r=json.loads(a.seal.read_text());cal=calibration_from(r['calibration']);b=cal.binding
if r['candidate']!=candidate_identity() or b.process_id==74438 or not -180<=a.heading<=180 or not -90<=a.pitch<=90:raise ValueError('Pose preparation identity/goal invalid')
root=a.root/uuid4().hex;root.mkdir(parents=True);cancel=threading.Event();holder=[None];record={'class':'pose_preparation_only','target':[a.heading,a.pitch],'candidate':candidate_identity(),'steps':[],'limits':{'max_pulse_units':16,'pulse_ms':120,'max_pulses':128,'max_seconds':180}}
def publish(g):
 holder[0]=g
 if cancel.is_set():g.cancel();raise ValueError('canceled')
def stop(*_):
 cancel.set()
 if holder[0]:holder[0].cancel()
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
started=time.monotonic();observer=None
try:
 h=activate_practice(b);resume_practice(h,b,root,cancel);observer=MinecraftCameraObserver(h,cal.environment,cal.calibration_id,root/'frames')
 record['readiness']=acquire_readiness(observer,b,cal.environment.controls_id,1,cancel,root/'readiness',publish_guard=publish,neutral_receipt=native_hid_receipt,feedback_identity=(cal.environment.sha256,cal.calibration_id))
 g=None
 for i in range(128):
  if cancel.is_set() or time.monotonic()-started>180:raise ValueError('Pose preparation bounded stop')
  if i%24==0:
   if g:g.cancel()
   g=CameraMotionGuard(b,1,cal.environment.controls_id,root/f'worker-{i//24}');publish(g)
  before=observer.observe(execution=True);before.require(time.monotonic(),.8,.1)
  errors=(heading_delta(a.heading,before.heading),a.pitch-before.pitch)
  if max(map(abs,errors))<=.15:record['final']=[before.heading,before.pitch];break
  axis=0 if abs(errors[0])>=abs(errors[1]) else 1
  units=max(1,min(16,round(abs(errors[axis])/.15)))*(1 if errors[axis]>0 else -1)
  now=time.monotonic();act=RelativePointerAction(units if axis==0 else 0,units if axis==1 else 0,120,now,now+.12,1,before.frame);step={'before':asdict(before),'action':asdict(act)};record['steps'].append(step)
  if cancel.is_set():raise ValueError('Pose canceled before posting')
  step['delivery']=g.pulse(act)
  if cancel.wait(.14):raise ValueError('Pose canceled after posting')
  after=observer.observe(execution=True);after.require(time.monotonic(),.8,.1);step['after']=asdict(after)
  measured=(heading_delta(after.heading,before.heading),after.pitch-before.pitch);expected=(act.dx*.15,act.dy*.15)
  if max(abs(x-y) for x,y in zip(measured,expected))>.3:raise ValueError('Contradictory pose response')
 else:raise ValueError('Pose finite displacement budget exhausted')
except Exception as exc:record['error']=str(exc)
finally:
 record['release']=holder[0].cancel() if holder[0] else {};record['canceled_at']=time.monotonic();record['native_neutral']=native_hid_receipt()
 try:
  first=observer.observe(execution=True);time.sleep(.2);last=observer.observe(execution=True);record['settling']=[asdict(first),asdict(last)]
 except Exception as exc:record['settling_error']=str(exc)
 (root/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'evidence':str(root/'attempt.json'),'error':record.get('error'),'final':record.get('final'),'pulses':len(record['steps'])}))
if record.get('error') or record.get('settling_error'):raise SystemExit(1)
