"""Bounded exploratory camera-only response; never final qualification."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from smb3_agent.camera_native_input import CameraMotionGuard, NATIVE_VERSION, settings_digest, settings_snapshot
from smb3_agent.feedback_contracts import CameraEnvironment, RelativePointerAction, ReadingState
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver, DETECTOR_VERSION
from smb3_agent.screen_host import MacSelectedWindowHost


from smb3_agent.camera_practice import environment


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--window',required=True);parser.add_argument('--dx',type=int,default=0)
    parser.add_argument('--dy',type=int,default=0);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    if args.pid==74438 or bool(args.dx)==bool(args.dy) or max(abs(args.dx),abs(args.dy))>16:
        raise ValueError('Only one small reviewed camera axis in dedicated process')
    out=args.root/uuid4().hex;out.mkdir(parents=True)
    start=subprocess.check_output(['ps','-p',str(args.pid),'-o','lstart='],text=True).strip()
    host=MacSelectedWindowHost(args.pid,start,args.window)
    observer=MinecraftCameraObserver(host,environment(),'exploratory-calibration/v1',out/'frames')
    first=observer.observe(execution=True)
    first.require(first.grounded_at,1.5,.1)
    guard=CameraMotionGuard(first.frame.binding,1,settings_digest(),out)
    record={'class':'exploratory_only','environment':asdict(environment()),'settings':settings_snapshot(),'before':asdict(first),'source_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/smb3_agent').glob('*camera*.py')}}
    try:
        # Guardian startup is outside freshness; take a new frame after arming.
        before=observer.observe(execution=True);before.require(before.grounded_at,1.5,.1)
        record['before']=asdict(before);record['before_timing']=observer.last_timing
        now=time.monotonic();action=RelativePointerAction(args.dx,args.dy,100,now,now+.1,1,before.frame)
        record['action']=asdict(action);record['delivery']=guard.pulse(action)
        time.sleep(.12)
        after=observer.observe(execution=True)
        record['after']=asdict(after);record['after_timing']=observer.last_timing
        record['after_visible']=asdict(observer.last_visible) if observer.last_visible else None
    except Exception as exc:
        record['error']=str(exc)
    finally:
        record['release']=guard.cancel()
        record['canceled_at']=time.monotonic()
        try:
            settle1=observer.observe(execution=True);time.sleep(.2);settle2=observer.observe(execution=True)
            record['settling']=[asdict(settle1),asdict(settle2)]
        except Exception as exc:
            record['settling_error']=str(exc)
        (out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'attempt':str(out/'attempt.json'),'error':record.get('error'),
        'before':[record['before']['heading'],record['before']['pitch']],
        'after':[record.get('after',{}).get('heading'),record.get('after',{}).get('pitch')],
        'release':record['release'],'timing':record.get('after_timing')}))


if __name__=='__main__':
    main()
