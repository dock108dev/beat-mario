"""Run the shipped setup script to verify immediate controls ignore draft errors."""

import json
import shutil
import subprocess

import pytest

from smb3_agent.player_setup_ui import PLAYER_SETUP_JS


NODE = shutil.which("node")
HARNESS = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let input='';process.stdin.on('data',v=>input+=v);process.stdin.on('end',async()=>{
 const {script,action,onboarding}=JSON.parse(input),nodes={},requests=[];
 const document={activeElement:null,getElementById:id=>nodes[id] ||= new Element(),createElement:()=>new Element()};
 class Element {
  constructor(){this.value='';this.textContent='';this.disabled=false;this.dataset={};this.listeners={};this.options=[];this.checked=false;}
  addEventListener(name,fn){this.listeners[name]=fn;}
  replaceChildren(...children){this.options=children;}
  focus(){document.activeElement=this;}
  blur(){if(document.activeElement===this)document.activeElement=null;}
 }
 const state={profiles:[],templates:{minecraft:{supported:[],unavailable:[]},openttd:{supported:[],unavailable:[]}},selected:null,messages:[],history:[],reason:'Ready',native_reason:'Ready'};
 if(onboarding){state.minecraft_onboarding={title:'<img src=x onerror=alert(1)>',next_action:'Connect the current window',steps:[{label:'Connection',status:'pending',detail:'<strong>Fresh check required</strong>'}],available_tasks:['Look right 2 degrees'],blocked_tasks:['Finish a wall']};}
 const root=document.getElementById('player-setup');root.dataset={state:JSON.stringify(state),csrf:'token'};
 document.getElementById('game').value='minecraft';
 const fetch=async(url,opts)=>{
  const body=new URLSearchParams(opts.body);
  requests.push({action:body.get('action'),payload:JSON.parse(body.get('payload'))});
  return {ok:true,json:async()=>state};
 };
 vm.runInNewContext(script,{document,fetch,URLSearchParams,crypto:{randomUUID:()=> 'page'},setInterval:()=>{},window:{addEventListener:()=>{}},navigator:{sendBeacon:()=>{}}});
 assert.equal(document.getElementById('minecraft-onboarding').hidden,!onboarding);
 if(onboarding){
  assert.equal(document.getElementById('mc-setup-title').textContent,'<img src=x onerror=alert(1)>');
  assert.equal(document.getElementById('mc-setup-next').textContent,'Connect the current window');
  assert.equal(document.getElementById('mc-setup-steps').options[0].textContent,'Connection · Later: <strong>Fresh check required</strong>');
  assert.equal(document.getElementById('mc-available-tasks').options[0].textContent,'Look right 2 degrees');
  assert.equal(document.getElementById('mc-blocked-tasks').options[0].textContent,'Finish a wall');
  document.getElementById('game').value='openttd';document.getElementById('game').listeners.change();
  assert.equal(document.getElementById('minecraft-onboarding').hidden,true);
  requests.length=0;
 }
 document.getElementById('mc-protected').value='not valid JSON';
 document.getElementById('mc-window').value='also invalid JSON';
 document.getElementById('mc-axis').value='x';
 document.getElementById('mc-disposable').checked=true;
 document.getElementById('request').disabled=true;
 const click=()=>root.listeners.click({target:{closest:()=>({dataset:{action}})}});
 click();
 for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));
 if(action==='scope'){
  assert.equal(requests.length,0);
  assert.equal(document.getElementById('error').textContent,'Protected cells must be a JSON list of coordinates');
  document.getElementById('mc-protected').value='[[3,-60,8]]';
  click();
  assert.equal(requests.length,1);
  assert.deepEqual(requests[0].payload,{client_id:'page',axis:'x',protected:[[3,-60,8]],disposable_confirmation:true});
 }else{
  assert.equal(requests.length,1);
  assert.equal(requests[0].action,action);
  if(['stop','reclaim','disconnect','chat','windows','save_workspace','minecraft_settings'].includes(action)){
   assert.deepEqual(requests[0].payload,{client_id:'page'});
  }else if(action==='protect'){
   assert.deepEqual(requests[0].payload,{client_id:'page',axis:'x',disposable_confirmation:true});
  }
  assert.equal(document.getElementById('error').textContent,'');
  if(action==='chat'){
   assert.equal(document.getElementById('request').disabled,false);
   assert.equal(document.activeElement,document.getElementById('request'));
  }
 }
});
"""


@pytest.mark.skipif(NODE is None, reason="Node is needed for shipped browser behavior")
@pytest.mark.parametrize(
    "action",
    ["stop", "reclaim", "disconnect", "chat", "windows", "save_workspace",
     "minecraft_settings", "protect", "scope"],
)
def test_setup_buttons_only_validate_fields_needed_for_the_action(action):
    result = subprocess.run(
        [NODE, "-e", HARNESS],
        input=json.dumps({"script": PLAYER_SETUP_JS, "action": action}),
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


FLOW_HARNESS = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
let input='';process.stdin.on('data',v=>input+=v);process.stdin.on('end',async()=>{
 const {script,scenario,action}=JSON.parse(input),nodes={},pending=[],intervals=[];
 const document={activeElement:null,getElementById:id=>nodes[id] ||= new Element(),createElement:()=>new Element()};
 class Element {
  constructor(){this.value='';this.textContent='';this.disabled=false;this.dataset={};this.listeners={};this.options=[];this.checked=false;}
  addEventListener(name,fn){this.listeners[name]=fn;}
  replaceChildren(...children){this.options=children;}
  focus(){document.activeElement=this;}
  blur(){if(document.activeElement===this)document.activeElement=null;}
 }
 const scope=protected=>({anchor:[0,0,0],axis:'x',material:'minecraft:stone',protected,stop_point:[0,0,0]});
 let state={profiles:[],templates:{minecraft:{supported:[],unavailable:[],surface:'/minecraft'}},selected:{id:'profile',game:'minecraft'},messages:[],history:[],reason:'Ready',native_reason:'Ready',minecraft:{state:'connected',busy:false,features:{camera:true},scope:scope([]),reason:'Ready',camera:{windows:[],sessions:[]}}};
 const root=document.getElementById('player-setup');root.dataset={state:JSON.stringify(state),csrf:'token'};
 document.getElementById('game').value='minecraft';
 const response=(s,ok=true)=>({ok,json:async()=>s});
 const fetch=async(url,opts)=>{
  if(!opts)return response(state);
  const body=new URLSearchParams(opts.body),action=body.get('action');
  return new Promise(resolve=>pending.push({action,payload:JSON.parse(body.get('payload')),resolve:(s=state,ok=true)=>resolve(response(s,ok))}));
 };
 vm.runInNewContext(script,{document,fetch,URLSearchParams,crypto:{randomUUID:()=> 'page'},setInterval:(f,ms)=>intervals.push({f,ms}),window:{addEventListener:()=>{}},navigator:{sendBeacon:()=>{}}});
 const settle=async()=>{for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));};
 const click=action=>root.listeners.click({target:{closest:()=>({dataset:{action}})}});
 const poll=async()=>{await intervals.find(i=>i.ms===500).f();await settle();};
 const field=document.getElementById('mc-protected'),draft=document.getElementById('request');
 document.getElementById('mc-axis').value='x';document.getElementById('mc-disposable').checked=true;
 if(scenario==='protected'){
  click('protect');assert.equal(pending[0].action,'protect');
  state={...state,minecraft:{...state.minecraft,state:'checking',busy:true}};
  pending.shift().resolve();await settle();
  state={...state,minecraft:{...state.minecraft,state:'connected',busy:false,scope:scope([[3,-60,8]])}};
  await poll();assert.equal(field.value,'[[3,-60,8]]');
  click('scope');assert.deepEqual(pending[0].payload.protected,[[3,-60,8]]);
  pending.shift().resolve();await settle();
  field.value='[[4,-60,8]]';field.listeners.input();
  state={...state,minecraft:{...state.minecraft,scope:scope([[3,-60,8],[5,-60,8]])}};
  await poll();assert.equal(field.value,'[[4,-60,8]]');
  click('scope');const check=pending.shift();assert.deepEqual(check.payload.protected,[[4,-60,8]]);
  state={...state,minecraft:{...state.minecraft,state:'checking',busy:true}};
  check.resolve();await settle();
  // Edits made while inspection is in progress remain an unsent draft.
  field.value='[[6,-60,8]]';field.listeners.input();
  state={...state,minecraft:{...state.minecraft,state:'connected',busy:false,scope:scope([[4,-60,8]])}};
  await poll();assert.equal(field.value,'[[6,-60,8]]');
  click('scope');const next=pending.shift();assert.deepEqual(next.payload.protected,[[6,-60,8]]);
  state={...state,minecraft:{...state.minecraft,scope:scope([[6,-60,8]])}};
  next.resolve();await settle();
  state={...state,minecraft:{...state.minecraft,scope:scope([[6,-60,8],[7,-60,8]])}};
  await poll();assert.equal(field.value,'[[6,-60,8],[7,-60,8]]');
 }else if(scenario==='lock'){
  draft.disabled=false;draft.focus();click(action);
  assert.equal(draft.disabled,true);assert.equal(document.activeElement,null);
  pending.shift().resolve();await settle();assert.equal(draft.disabled,true);
  click('chat');pending.shift().resolve({error:'Release unconfirmed'},false);await settle();assert.equal(draft.disabled,true);
  click('chat');pending.shift().resolve();await settle();assert.equal(draft.disabled,false);assert.equal(document.activeElement,draft);
 }else if(scenario==='late_start'){
  draft.disabled=false;draft.focus();click('start');const start=pending.shift();
  click('stop');pending.shift().resolve({...state,reason:'Stopped'});await settle();
  start.resolve({...state,reason:'Old executing response',reviewed:true,plan:{executable:true}});await settle();
  assert.equal(document.getElementById('reason').textContent,'Stopped');assert.equal(draft.disabled,true);assert.equal(document.getElementById('mc-start').disabled,true);
 }else if(scenario==='late_chat'){
  draft.disabled=true;click('chat');const chat=pending.shift();
  click('start');const start=pending.shift();chat.resolve();await settle();
  assert.equal(draft.disabled,true);assert.notEqual(document.activeElement,draft);
  start.resolve();await settle();assert.equal(draft.disabled,true);
 }
});
"""


@pytest.mark.skipif(NODE is None, reason="Node is needed for shipped browser behavior")
@pytest.mark.parametrize(
    ("scenario", "action"),
    [("protected", "scope"), ("lock", "start"), ("lock", "calibrate"),
     ("lock", "scope"), ("lock", "protect"), ("late_start", "start"),
     ("late_chat", "chat")],
)
def test_setup_protection_drafts_native_input_lock_and_late_responses(scenario, action):
    result = subprocess.run(
        [NODE, "-e", FLOW_HARNESS],
        input=json.dumps({"script": PLAYER_SETUP_JS, "scenario": scenario, "action": action}),
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(NODE is None, reason="Node is needed for shipped browser behavior")
def test_minecraft_setup_progress_renders_server_guidance_as_plain_text():
    result = subprocess.run(
        [NODE, "-e", HARNESS],
        input=json.dumps({"script": PLAYER_SETUP_JS, "action": "stop", "onboarding": True}),
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
