"""Explicit menu/capture diagnostic, no qualification or world interaction."""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time
from smb3_agent.camera_practice import activate_practice, resume_practice
from smb3_agent.feedback_contracts import WindowBinding
from smb3_agent.screen_host import MacSelectedWindowHost

p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--window',required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--axis',choices=['dx','dy'],required=True);p.add_argument('--units',type=int,choices=[-4,4],required=True);a=p.parse_args()
a.root.mkdir(parents=True,exist_ok=False)
start=subprocess.check_output(['ps','-p',str(a.pid),'-o','lstart='],text=True).strip()
b=WindowBinding(a.pid,start,a.window,(329,223,854,508),(1708,1016))
h=activate_practice(b)
# Exact visible menu-only resume. A pause is first explicitly entered if needed.
import Quartz as q
if not q.CGCursorIsVisible():
 subprocess.run(['.venv/bin/python','scripts/pb7m_prepare.py','--pid',str(a.pid),'--window',a.window,'--root',str(a.root/'menu'),'--key','escape'],check=True)
resume_practice(h,b,a.root,threading.Event())
for n in range(2):
 r=subprocess.run(['.venv/bin/python','scripts/pb7m_diagnose.py','--pid',str(a.pid),'--window',a.window,'--root',str(a.root/('first' if n==0 else 'second')),'--'+a.axis,str(a.units),'--wait-before','5' if n==0 else '0'],text=True,capture_output=True)
 (a.root/f'run-{n}.log').write_text(r.stdout+r.stderr)
 print(r.stdout,flush=True)
 if r.returncode or '"error": null' not in r.stdout:raise RuntimeError('Diagnostic failed; stop group')
