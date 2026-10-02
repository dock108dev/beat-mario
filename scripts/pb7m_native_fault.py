"""Explicit native qualification fault on one exact dedicated window.

Wait for a new ordinary-panel correction worker and its delivered pulse, then
perform one authorized menu/focus/window/process fault. No camera input is
emitted. The panel alone owns camera authority and cancellation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import AppKit
import ApplicationServices as ax
import Quartz as q
from smb3_agent.camera_native_input import NATIVE_VERSION
from smb3_agent.camera_practice import candidate_identity
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--pid',type=int,required=True);p.add_argument('--window',required=True);p.add_argument('--mode',choices=['menu','focus','window','process'],required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
if a.pid==74438:raise ValueError('Personal process excluded')
existing=set((a.root/'runs').glob('*/native-motion.jsonl'));begin=time.monotonic()
while time.monotonic()-begin<30:
 for path in set((a.root/'runs').glob('*/native-motion.jsonl'))-existing:
  try:rows=[json.loads(x) for x in path.read_text().splitlines()]
  except (OSError,ValueError):continue
  if not rows or rows[0].get('implementation')!=NATIVE_VERSION:continue
  arms=[r for r in rows if r['kind']=='armed' and r['binding']['process_id']==a.pid and r['binding']['window_id']==a.window]
  deliveries=[r for r in rows if r['kind']=='delivered']
  if not arms or not deliveries:continue
  binding=arms[0]['binding']
  started=subprocess.check_output(['ps','-p',str(a.pid),'-o','lstart='],text=True).strip()
  windows=q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly,q.kCGNullWindowID) or ()
  match=[r for r in windows if r.get(q.kCGWindowOwnerPID)==a.pid and str(r.get(q.kCGWindowNumber))==a.window]
  if started!=binding['process_started_at'] or len(match)!=1 or AppKit.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()!=a.pid:raise ValueError('Fault binding/foreground changed before reviewed fault')
  app=ax.AXUIElementCreateApplication(a.pid);err,aw=ax.AXUIElementCopyAttributeValue(app,ax.kAXWindowsAttribute,None)
  selected=[]
  for w in aw or ():
   e,title=ax.AXUIElementCopyAttributeValue(w,ax.kAXTitleAttribute,None)
   if title==match[0].get(q.kCGWindowName):selected.append(w)
  if err or len(selected)!=1:raise ValueError('Exact native fault window unavailable')
  record={'class':'native_fault_producer_only','candidate':candidate_identity(),'mode':a.mode,'binding':binding,'epoch':arms[0]['epoch'],'native_log':str(path),'last_delivery':deliveries[-1],'fault_started_at':time.monotonic(),'wall_started_ns':time.time_ns(),'camera_input_emitted':False}
  if a.mode=='menu':
   for down in (True,False):q.CGEventPost(q.kCGHIDEventTap,q.CGEventCreateKeyboardEvent(None,53,down))
  elif a.mode=='focus':
   target=AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(73996)
   if target is None:raise ValueError('Reviewed official launcher focus target absent')
   target.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
  elif a.mode=='window':
   error=ax.AXUIElementSetAttributeValue(selected[0],ax.kAXMinimizedAttribute,True)
   if error:raise ValueError(f'Minimize failed {error}')
  else:
   error,button=ax.AXUIElementCopyAttributeValue(selected[0],ax.kAXCloseButtonAttribute,None)
   if error:raise ValueError('Native window close unavailable')
   error=ax.AXUIElementPerformAction(button,ax.kAXPressAction)
   if error:raise ValueError(f'Native close failed {error}')
  record['fault_returned_at']=time.monotonic();record['wall_returned_ns']=time.time_ns()
  a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(0)
 time.sleep(.002)
raise SystemExit('No eligible delivered correction before deadline; no fault applied')
