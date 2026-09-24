"""Behavior tests for the ordinary conversation UI's stable polling boundary."""

from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from smb3_agent.conversation_ui import CONVERSATION_JS, render_conversation_workspace


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.initial = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(str(attributes["id"]))
        if attributes.get("data-initial-state"):
            self.initial = str(attributes["data-initial-state"])


def test_conversation_shell_has_safe_initial_state_and_explicit_launch() -> None:
    state = {"plan": {"requested_objective": '<script>alert("x")</script>',
                      "base_route_id": "world_8_finish_game"}}
    rendered = render_conversation_workspace(state, csrf_token='test"token')
    page = Page()
    page.feed(rendered)
    assert json.loads(page.initial) == state
    assert len(page.ids) == len(set(page.ids))
    assert '<script>alert("x")</script>' not in rendered
    assert 'name="allow_takeover" value="true"' in rendered
    assert 'name="pause_for_plan" value="true"' in rendered
    assert 'action="/observe-start"' in rendered
    assert 'value="turbo"' in rendered
    assert 'value="2"' not in rendered
    assert 'data-conversation-action="reclaim"' in rendered
    assert 'data-conversation-action="pause"' in rendered
    assert 'data-conversation-action="stop"' in rendered


NODE = shutil.which("node")
HARNESS = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
 const {script, scenario} = JSON.parse(input);
 const handlers = {};
 const nodes = {};
 const document = {activeElement:null, hidden:false, addEventListener:() => {},
   getElementById:id => nodes[id], createElement:tag => new Element(tag)};
 class Element {
   constructor(tag) {this.tagName=tag.toUpperCase();this.value='';this.textContent='';this.dataset={};this.children=[];this.hidden=false;this.disabled=false;this.scrollHeight=100;this.scrollTop=0;this.clientHeight=100;this.selectionStart=0;this.selectionEnd=0;}
   replaceChildren(...children) {this.children=children; if(this.tagName==='SELECT')this.value=children[0]?.value||'';}
   addEventListener(name, callback) {this.listeners ||= {};this.listeners[name]=callback;}
   append(...children) {this.children.push(...children);}
   focus() {document.activeElement=this;}
 }
 class Form extends Element {
   constructor(action, fields) {super('form');this.dataset.conversationForm=action;this.fields=fields;this.button=new Element('button');}
   querySelectorAll() {return [this.button];}
 }
 const root=new Element('section'); root.dataset={csrf:'secret',initialState:'{}'};
 root.addEventListener=(name,callback) => {handlers[name]=callback;};
 root.contains=() => true;
 root.querySelector=()=>nodes['conversation-open-game'];
 nodes['mario-conversation']=root;
 for(const name of ['owner','session','requested','loaded','fallback','plan-label','actions','eligibility','unsupported','current','pending','boundary','ack','speed-status','performance','live-reason','open-game','messages','variant','outcome','coverage','history','details','error','draft','variant-name','intent','speed','revision','revisions','earlier','older-messages','playing','controls']) nodes['conversation-'+name]=new Element(name==='variant'?'select':'div');
 let interval;
 let serverState={plan:{plan_id:'rendered-plan-2',revision:2,requested_objective:'Quickest',base_route_id:'world_8_finish_game',fallback_explanation:'Optimized variant unavailable',actions:[]},runtime:{owner:'agent',revision:1,requested_speed:'turbo',applied_speed:'turbo'},messages:[],variants:[{variant_id:'a',name:'A'},{variant_id:'b',name:'B'}]};
 const calls=[];let postResolve;
 const response = data => ({ok:true, headers:{get:()=> 'application/json'},json:async()=>data});
 const fetch=async(url,options={}) => {calls.push({url,options});if(options.method==='POST')return new Promise(resolve=>{postResolve=()=>resolve(response(serverState));});return response(serverState);};
 class FormData {constructor(form){this.fields={...form.fields};if(form.dataset.conversationForm==='message')this.fields.text=nodes['conversation-draft'].value;} [Symbol.iterator](){return Object.entries(this.fields)[Symbol.iterator]();}}
 const context={document,fetch,HTMLFormElement:Form,FormData,URLSearchParams,crypto:{randomUUID:()=> 'request-unique'},window:{setInterval:fn=>{interval=fn;}}};
 vm.runInNewContext(script,context);
 const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
 await settle();
 const draft=nodes['conversation-draft'];draft.value='Please change my future path';draft.selectionStart=7;draft.selectionEnd=13;draft.focus();
 const original=draft;
 if(scenario.endsWith('-toolbar')) {
   const action=scenario.replace('-toolbar','');
   nodes['conversation-controls'].listeners.click({target:{closest:()=>({dataset:{conversationAction:action}})}});
   await settle();postResolve();await settle();
   const sent=new URLSearchParams(calls.find(call=>call.options.method==='POST').options.body);
   assert.equal(sent.get('action'),action);assert.equal(sent.get('csrf_token'),'secret');
   assert.equal(document.activeElement,original);
 } else if(scenario==='polling') {
   nodes['conversation-variant'].value='b';nodes['conversation-intent'].value='100% clear';
   serverState={...serverState,runtime:{...serverState.runtime,revision:3},messages:[{role:'assistant',text:'<img src=x onerror=alert(1)>'}]};
   await interval();await settle();
   assert.equal(document.activeElement,original);assert.equal(draft.value,'Please change my future path');assert.equal(draft.selectionStart,7);assert.equal(draft.selectionEnd,13);
   assert.equal(nodes['conversation-variant'].value,'b');assert.equal(nodes['conversation-intent'].value,'100% clear');
   assert.equal(nodes['conversation-ack'].textContent,'Game confirmed plan version 3.');
   assert.equal(nodes['conversation-messages'].children[0].children[1].textContent,'<img src=x onerror=alert(1)>');
   assert.match(nodes['conversation-speed-status'].textContent,/Faster \(uncapped\)/);
 } else if(scenario==='pending-boundary') {
   serverState={...serverState,plan:{...serverState.plan,effective_boundary:'world_1_1_opening'},pending_plan:{revision:3,effective_boundary:'world_1_1_opening'},runtime:{...serverState.runtime,effective_boundary:'world_1_1_opening',pending:{revision:3,effective_boundary:'world_1_1_exit'}}};
   await interval();await settle();
   assert.equal(nodes['conversation-boundary'].textContent,'Change takes effect at: World 1-1 exit');
   assert.equal(document.activeElement,original);assert.equal(draft.selectionStart,7);assert.equal(draft.selectionEnd,13);
   serverState={...serverState,pending_plan:{revision:3,effective_boundary:'world_1_1_exit'},runtime:{...serverState.runtime,pending:null}};
   await interval();await settle();
   assert.equal(nodes['conversation-boundary'].textContent,'Change takes effect at: World 1-1 exit');
 } else {
   const reviewed=scenario==='reviewed-start'||scenario==='reviewed-apply';
   if(reviewed){serverState={...serverState,plan:{...serverState.plan,plan_id:'rendered-plan-3',revision:3}};await interval();await settle();}
   const form=reviewed?new Form(scenario==='reviewed-start'?'start':'apply',{}):scenario==='normal-speed'?new Form('speed',{rate:'1'}):new Form('message',{});const event={target:form,preventDefault:()=>{}};
   const first=handlers.submit(event);await settle();
   if(scenario==='duplicate') {await handlers.submit(event);await interval();assert.equal(calls.filter(call=>call.options.method==='POST').length,1);}
   if(scenario==='new-draft') {draft.value='A new request typed while sending';draft.selectionStart=4;draft.selectionEnd=8;}
   postResolve();await first;await settle();
   const sent=new URLSearchParams(calls.find(call=>call.options.method==='POST').options.body);
   assert.equal(sent.get('csrf_token'),'secret');assert.equal(JSON.parse(sent.get('payload')).request_id,'request-unique');
   assert.equal(document.activeElement,original);
   if(reviewed){const payload=JSON.parse(sent.get('payload'));assert.equal(payload.expected_plan_id,'rendered-plan-3');assert.equal(payload.expected_revision,3);assert.equal(draft.value,'Please change my future path');}
   else if(scenario==='normal-speed'){assert.equal(JSON.parse(sent.get('payload')).rate,1);assert.equal(draft.value,'Please change my future path');}
   else if(scenario==='new-draft'){assert.equal(draft.value,'A new request typed while sending');assert.equal(draft.selectionStart,4);assert.equal(draft.selectionEnd,8);}else{assert.equal(draft.value,'');}
 }
});
'''


@pytest.mark.skipif(NODE is None, reason="Node.js is needed for browser behavior checks")
@pytest.mark.parametrize("scenario", ["polling", "duplicate", "new-draft", "normal-speed", "reviewed-start", "reviewed-apply", "pending-boundary", "reclaim-toolbar", "stop-toolbar", "pause-toolbar", "resume-toolbar"])
def test_shipped_conversation_polling_and_submit_behavior(scenario: str) -> None:
    result = subprocess.run(
        [str(NODE), "-e", HARNESS],
        input=json.dumps({"script": CONVERSATION_JS, "scenario": scenario}),
        text=True, capture_output=True, check=False, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_conversation_http_contract_keeps_controls_available_and_csrf(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    import http.client
    import threading
    from urllib.parse import urlencode

    from smb3_agent import lab_ui

    class FakeConversationService:
        def __init__(self, live_manager, *, artifacts_root) -> None:
            self.manager = live_manager
            self.artifacts_root = artifacts_root
            self.calls = []

        def snapshot(self):
            return {"messages": [], "plan": {"requested_objective": "quickest",
                    "fallback_explanation": "Optimized variant unavailable",
                    "base_route_id": "world_8_finish_game"}}

        def close(self):
            pass

        def dispatch(self, action, payload):
            if action == "invalid":
                raise ValueError("Unsupported conversation action")
            self.calls.append((action, payload))
            return self.snapshot()

    monkeypatch.setattr(lab_ui, "ConversationService", FakeConversationService)
    monkeypatch.setattr(lab_ui, "ARTIFACT_DIR", tmp_path)
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, data=None, *, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if host:
            headers["Host"] = host
        connection.request(method, path, body=urlencode(data) if data else None, headers=headers)
        response = connection.getresponse()
        body = response.read().decode()
        connection.close()
        return response.status, body

    try:
        status, page = request("GET", "/mario")
        assert status == 200
        assert page.index('id="mario-conversation"') < page.index('id="active-workspace"')
        assert 'src="/assets/conversation.js"' in page
        assert "Optimized variant unavailable" in page
        assert server.conversation_service.manager is server.live_observation_manager
        status, body = request("GET", "/api/conversation")
        assert status == 200
        assert json.loads(body)["plan"]["base_route_id"] == "world_8_finish_game"
        status, body = request("GET", "/assets/conversation.js")
        assert status == 200 and body == CONVERSATION_JS
        status, _ = request("POST", "/api/conversation", {"action": "reclaim"})
        assert status == 403 and not server.conversation_service.calls
        status, _ = request("GET", "/api/conversation", host="outside.example")
        assert status == 403
        server.action_lock.acquire()
        try:
            status, _ = request("POST", "/api/conversation", {
                "csrf_token": server.csrf_token, "action": "reclaim",
                "payload": json.dumps({"request_id": "reclaim-1"}),
            })
        finally:
            server.action_lock.release()
        assert status == 200
        assert server.conversation_service.calls == [("reclaim", {"request_id": "reclaim-1"})]
        status, body = request("POST", "/api/conversation", {
            "csrf_token": server.csrf_token, "action": "invalid", "payload": "{}",
        })
        assert status == 400 and json.loads(body)["error"] == "Unsupported conversation action"
        status, body = request("POST", "/api/conversation", {
            "csrf_token": server.csrf_token, "action": "message", "payload": "[]",
        })
        assert status == 400 and "must be an object" in json.loads(body)["error"]
        server.catalog_session.preferences.selected_adapter_id = "stardew"
        status, body = request("POST", "/api/conversation", {
            "csrf_token": server.csrf_token, "action": "start", "payload": "{}",
        })
        assert status == 400 and "Select Mario" in json.loads(body)["error"]
        status, _ = request("POST", "/api/conversation", {
            "csrf_token": server.csrf_token, "action": "stop", "payload": "{}",
        })
        assert status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_shutdown_retains_outcome_after_neutralization_even_if_initial_stop_fails(monkeypatch):
    from types import SimpleNamespace

    from smb3_agent import lab_ui

    events = []

    class Service:
        def close(self):
            events.append("stop_requested")
            raise ValueError("Fixture stop request failure")

        def snapshot(self):
            events.append("outcome_retained")

    class Manager:
        def __init__(self, name):
            self.name = name

        def shutdown(self):
            events.append(self.name)

    monkeypatch.setattr(lab_ui, "ConversationService", Service)
    monkeypatch.setattr(lab_ui, "ShowSessionManager", Manager)
    monkeypatch.setattr(lab_ui, "LiveObservationManager", Manager)
    server = SimpleNamespace(conversation_service=Service(), show_manager=Manager("show_stopped"),
                             live_observation_manager=Manager("live_neutralized"))
    lab_ui._shutdown_session_managers(server)
    assert events == ["stop_requested", "show_stopped", "live_neutralized", "outcome_retained"]
