"""Execute the shipped browser script against delayed responses and routine polls."""
import json
import shutil
import subprocess

import pytest

from smb3_agent.profile_conversation_ui import PROFILE_CONVERSATION_JS

NODE = shutil.which('node')
HARNESS = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
let input='';process.stdin.on('data',v=>input+=v);process.stdin.on('end',async()=>{
 const {script,scenario}=JSON.parse(input),nodes={},handlers={},intervals=[],pending=[];
 const document={activeElement:null,getElementById:id=>nodes[id],createElement:tag=>new Element(tag)};
 class Element {
  constructor(tag){this.tagName=tag.toUpperCase();this.dataset={};this.listeners={};this.disabled=false;this.value='';this.textContent='';this.children=[];this.selectionStart=2;this.selectionEnd=5;}
  addEventListener(n,f){this.listeners[n]=f;}
  replaceChildren(...v){this.children=v;if(this.tagName==='SELECT')this.value=v[0]?.value||'';}
  focus(){document.activeElement=this;}
  blur(){if(document.activeElement===this)document.activeElement=null;}
 }
 class Form extends Element {constructor(action){super('form');this.dataset.action=action;}}
 const root=new Element('section');root.dataset={csrf:'token',selected:'true',initialState:'{}'};root.addEventListener=(n,f)=>handlers[n]=f;
 nodes['profile-workspace']=root;
 for(const id of ['status','reason','owner','profile','window','chat','send','review','start','connect','launch','permissions','connection-state','plan','values','review-state','outcome','messages','history','diagnostics','error','draft'])nodes['profile-'+id]=new Element(['window','profile'].includes(id)?'select':'div');
 const draft=nodes['profile-draft'];draft.disabled=true;
 let state={connected:true,client_matches:'page',state:'Connected',runtime:{owner:'player',permissions:{capture:true,input:true},neutralized:true},profiles:[{id:'profile',label:'Supported'}],windows:[{pid:1,started:'start',window_id:'7',label:'Exact'}],messages:[],history:[]};
 const response=s=>({ok:true,json:async()=>s});
 const fetch=async(url,opts={})=>{
  if(!opts.method)return response(state);
  const body=new URLSearchParams(opts.body),action=body.get('action');
  if(['windows','heartbeat','ui_timing'].includes(action))return response(state);
  return new Promise(resolve=>pending.push({action,resolve:s=>resolve(response(s)),payload:JSON.parse(body.get('payload'))}));
 };
 const context={document,fetch,HTMLFormElement:Form,URLSearchParams,crypto:{randomUUID:()=> 'page'},performance:{now:()=>1},navigator:{sendBeacon:()=>{}},setInterval:(f,ms)=>intervals.push({f,ms}),window:{addEventListener:()=>{}}};
 vm.runInNewContext(script,context);
 const settle=async()=>{for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));};await settle();
 const click=action=>handlers.click({target:{closest:()=>({dataset:{action}})}});
 const poll=async()=>{await intervals.find(i=>i.ms===250).f();await settle();};
 click('chat');await settle();assert.equal(draft.disabled,true);assert.equal(document.activeElement,null);
 pending.shift().resolve({...state,control_receipt:{confirmed:true,control_id:'chat'}});await settle();
 assert.equal(draft.disabled,false);assert.equal(document.activeElement,draft);
 draft.value='repay once';
 if(scenario==='polling'){
  state={...state,state:'Ready to start',plan:{plan_id:'p',revision:1,actions:[{}]},reviewed:true,proposal_current:true};
  await poll();assert.equal(draft.value,'repay once');assert.equal(draft.selectionStart,2);assert.equal(document.activeElement,draft);
  draft.value='do not repay';draft.listeners.input();await settle();
  assert.equal(pending[0].action,'edit');await poll();assert.equal(nodes['profile-start'].disabled,true);
  assert.equal(draft.value,'do not repay');assert.equal(draft.selectionStart,2);
 }else if(scenario==='priority'){
  handlers.submit({preventDefault:()=>{},target:new Form('message')});await settle();assert.equal(pending[0].action,'message');
  click('stop');await settle();assert.equal(pending[1].action,'stop');
  pending[1].resolve({...state,state:'Stopped',plan:null,control_receipt:{confirmed:true,control_id:'stop'}});await settle();
  pending[0].resolve({...state,state:'Ready to start',plan:{actions:[{}]},reviewed:true});await settle();
  assert.equal(root.dataset.state,'Stopped');assert.equal(nodes['profile-start'].disabled,true);
 }else if(scenario==='start'){
  state={...state,state:'Ready to start',plan:{plan_id:'p',revision:2,actions:[{}]},reviewed:true,proposal_current:true};await poll();
  click('start');await settle();assert.equal(draft.disabled,true);assert.equal(document.activeElement,null);
  assert.equal(pending[0].payload.expected_plan_id,'p');assert.equal(pending[0].payload.expected_revision,2);
 }else if(scenario==='selection'){
  state={...state,plan:{actions:[{}]},reviewed:true,proposal_current:true};await poll();nodes['profile-window'].listeners.change();await settle();
  await poll();assert.equal(nodes['profile-start'].disabled,true);assert.equal(pending[0].action,'edit');
 }
});
'''


@pytest.mark.skipif(NODE is None, reason='Node needed for shipped browser behavior')
@pytest.mark.parametrize('scenario',['polling','priority','start','selection'])
def test_profile_browser_focus_drafts_priority_and_late_responses(scenario):
    result = subprocess.run([NODE,'-e',HARNESS],input=json.dumps({'script':PROFILE_CONVERSATION_JS,'scenario':scenario}),
        text=True,capture_output=True,timeout=5)
    assert result.returncode == 0,result.stderr
