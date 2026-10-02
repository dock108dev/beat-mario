"""Index exact frozen-core goal histories; no input and no promotion of extras."""
import json
from pathlib import Path
r=Path('artifacts/private-beta/pb7m-camera/r1')
m=json.loads((r/'qualification-frozen.json').read_text())
p=r/'qualification-index.json';old=json.loads(p.read_text());core=[];extras=[];counts={}
for h in sorted((r/'history').glob('*.json'),key=lambda p:p.stat().st_mtime):
 v=json.loads(h.read_text())
 if v['candidate']!=m['candidate']:continue
 target=[v['review']['goal']['heading'],v['review']['goal']['pitch']]
 matches=[]
 for c in m['core_cases']:
  variants=c.get('variants',[c])
  for variant in variants:
   if variant['target']==target:matches.append((c,variant))
 if len(matches)!=1:extras.append({'history':v['attempt_id'],'session':v['session_id'],'target':target,'status':v['status']});continue
 c,variant=matches[0];key=(v['session_id'],c['id']);counts[key]=counts.get(key,0)+1
 initial=v.get('initial',{});i=[initial.get('heading'),initial.get('pitch')]
 from smb3_agent.feedback_contracts import heading_delta
 start_ok=all(x is not None for x in i) and max(abs(heading_delta(i[0],variant['initial'][0])),abs(i[1]-variant['initial'][1]))<=.15000001
 core.append({'kind':'core','session':v['session_id'],'case':c['id'],'repetition':counts[key],'history':v['attempt_id'],
  'requested_initial':variant['initial'],'observed_initial':i,'start_within_quantization':start_ok,'target':target,
  'status':v['status'],'result':v['result'],'evidence_path':str(h)})
faults=[t for t in old['trials'] if t['kind']!='core']
old['trials']=core+faults;old['extra_history']=extras;old['core_executed']=len(core)
old['core_verified']=sum(t['status']=='verified_completion' and t['result']['neutral_handback_confirmed'] and t['start_within_quantization'] for t in core)
old['remaining_core']=m['core_denominator']-len(core)
p.write_text(json.dumps(old,indent=2)+'\n');print(json.dumps({k:old[k] for k in ['core_executed','core_verified','remaining_core']}))
