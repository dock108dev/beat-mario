"""Reviewed native fault producer: suspend one exact owned correction emitter.

No game input is emitted. The ordinary panel must perform cancellation; already
posted events cannot be retracted. This producer itself is diagnostic evidence.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from smb3_agent.camera_practice import candidate_identity
from smb3_agent.camera_native_input import NATIVE_VERSION
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--pid',type=int,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
existing=set((a.root/'runs').glob('*/native-motion.jsonl'));start=time.monotonic()
while time.monotonic()-start<30:
 for path in set((a.root/'runs').glob('*/native-motion.jsonl'))-existing:
  try:rows=[json.loads(line) for line in path.read_text().splitlines()]
  except (OSError,ValueError):continue
  if not rows or rows[0].get('implementation')!=NATIVE_VERSION:continue
  armed=[r for r in rows if r['kind']=='armed' and r['binding']['process_id']==a.pid]
  if not armed:continue
  if any(r['kind']=='delivered' for r in rows):raise RuntimeError('Fault fixture missed pre-dispatch boundary; no suspension')
  worker=rows[0]['pid'];os.kill(worker,signal.SIGSTOP)
  state=subprocess.check_output(['ps','-p',str(worker),'-o','state='],text=True).strip()
  record={'class':'diagnostic_fault_producer_only','candidate':candidate_identity(),'worker_pid':worker,'native_log':str(path),'binding':armed[0]['binding'],'epoch':armed[0]['epoch'],'paused_at':time.monotonic(),'wall_paused_ns':time.time_ns(),'worker_state':state,'max_wait_seconds':30,'game_input_emitted':False,'requires_ordinary_panel_cancellation':True}
  a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True);raise SystemExit(0)
 time.sleep(.002)
raise SystemExit('No eligible fresh correction emitter; no fault applied')
