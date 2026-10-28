"""Served Minecraft chat behavior; kept as a Python asset for frozen packaging.

The HTML renderer and HTTP route import this constant without parsing a document.
Session credentials come from the escaped document dataset, never script text.
"""

CHAT_JS = r"""
const token=document.body.dataset.token, $=id=>document.getElementById(id);
let sid=null,url=null,shown=true,known=new Set(),sending=false,localError='',connectionError='';
$('draft').value=sessionStorage.getItem('minecraft-draft')||'';
$('draft').oninput=()=>sessionStorage.setItem('minecraft-draft',$('draft').value);
async function command(action,extra={}){
  const r=await fetch('/api/minecraft/chat',{
    method:'POST',headers:{
      'Content-Type':'application/x-www-form-urlencoded'
    },body:new URLSearchParams({
      csrf_token:token,action,session_id:sid||'',...extra
    })
  });
  const value=await r.json();
  if(!r.ok||value.error)throw Error(value.error||'Request failed');
  localError='';
  return value;
}
function failure(e){
  localError=e.message;
  $('error').textContent=e.message;
}
$('game').onchange=()=>{
  if($('game').value==='minecraft')$('setup-panel').hidden=false;
};
$('open-world').onclick=()=>command('connect',{
  world:$('world').value
}).catch(failure);
$('create-world').onclick=()=>command('connect',{
  world:$('world').value,create:'true',accept_eula:String($('eula').checked)
}).catch(failure);
$('sign-in').onclick=()=>command('sign_in').catch(failure);
$('check-setup').onclick=()=>command('check_setup').catch(failure);
$('quit').onclick=async()=>{
  try{
    const d=await(await fetch('/api/delivery')).json();
    const r=await fetch('/api/delivery/shutdown',{
      method:'POST',body:new URLSearchParams({
        csrf_token:token,instance:d.instance
      })
    });
    if(!r.ok)throw Error('Quit could not be confirmed. Use the app’s Quit button.');
    $('activity').textContent='App closed. Reopen Game Companion to return.';
  } catch(e){
    failure(e);
  }
};
$('stop').onclick=()=>{
  $('activity').textContent='Stopping…';
  $('send').disabled=true;
  command('stop').catch(failure);
};
$('reconnect').onclick=()=>command('reconnect').catch(failure);
$('toggle').onclick=()=>{
  shown=!shown;
  $('live-panel').hidden=!shown;
  $('view').src=shown?(url||'about:blank'):'about:blank';
  $('toggle').textContent=shown?'Close view':'Reopen view';
};
$('compose').onsubmit=async e=>{
  e.preventDefault();
  if(sending)return;
  const text=$('draft').value;
  if(!text.trim())return;
  sending=true;
  try{
    await command('message',{
      text,request_id:crypto.randomUUID()
    });
    if($('draft').value===text){
      $('draft').value='';
      sessionStorage.removeItem('minecraft-draft');
    }
    $('error').textContent='';
  } catch(e){
    failure(e);
  } finally{
    sending=false;
  }
};
async function refresh(){
  try{
    const r=await fetch('/api/minecraft/chat');
    if(!r.ok)throw Error('Connection status unavailable; use Stop and check the app.');
    const s=await r.json();
    sid=s.session_id;
    $('world').disabled=!!sid||s.connecting;
    if(sid)$('game').value='minecraft';
    const state=s.state;
    if(state.game_mode)$('world').value=state.game_mode;
    const setup=s.setup||{},w=(setup.worlds||{})[$('world').value];
    $('open-world').disabled=s.connecting||!!sid||!w?.ready;
    $('create-world').disabled=s.connecting||!!sid||w?.exists;
    $('setup-panel').hidden=!!state.ready;
    document.body.dataset.connected=String(!!state.ready);
    $('live-panel').hidden=!shown||(!sid&&!s.connecting);
    $('session-tools').hidden=!sid&&!s.connecting&&!s.error&&!s.connection_fault;
    $('toggle').disabled=!state.viewer_url;
    $('activity-panel').hidden=!sid&&!s.connecting;
    $('sign-in').hidden=!!s.codex.available;
    $('get-codex').hidden=!!s.codex.available;
    $('get-java').hidden=!!setup.java?.ready;
    $('setup-links').hidden=!!s.codex.available&&!!setup.java?.ready;
    $('setup-status').textContent=[!setup.node?.ready?setup.node?.message:null,!setup.java?.ready?setup.java?.message:null,w?.ready?'Your saved world is ready.':w?.message].filter(Boolean).join(' · ');
    $('empty-chat').hidden=s.messages.length>0;
    $('empty-chat').lastChild.textContent=state.ready?'Ask a question or give your companion a goal.':'Open a world to explore, gather or build together.';
    $('connection').textContent=s.connecting?'Connecting…':state.ready?'Connected':'Disconnected';
    $('identity').textContent=state.ready&&state.character?state.character+' · '+(state.game_mode||'Practice')+' world':'Minecraft';
    $('activity').textContent=s.activity;
    $('progress').textContent=s.progress||'';
    $('goal').textContent=s.goal?s.goal:'';
    $('codex').textContent=s.codex.message;
    $('pending').textContent=s.stopping?'Stopping · draft retained; send after confirmation':s.stop_failed?'Stop unconfirmed · reconnect before sending':s.busy?(state.active||s.goal?'Thinking · current task continues':'Thinking…'):'';
    $('send').disabled=s.busy||s.stopping||s.stop_failed||!state.ready||s.connecting;
    $('reconnect').disabled=s.connecting;
    $('send-status').textContent=s.stopping?'Wait for Stop to finish.':s.stop_failed?'Reconnect to continue.':s.connecting?'Connecting to your world…':!state.ready?'Open a world to send a message.':s.busy?'You can keep editing your draft.':'';
    connectionError='';
    $('error').textContent=[...new Set([localError,s.error].filter(Boolean))].join('\n');
    if(state.viewer_url!==url){
      url=state.viewer_url;
      if(shown)$('view').src=url||'about:blank';
    }
    $('viewer-status').textContent=!state.ready?'Bot disconnected':!shown?'View closed · bot connection stays active':state.viewer_clients?'Live bot view':state.ready?'Viewer unavailable or loading · bot connection remains active':'';
    $('details').textContent=JSON.stringify({
      session:sid,version:state.game_version,position:state.position,players:state.players,revision:state.revision
    },null,2);
    const memory=$('memory-recovery');
    const hasProblem=Object.values(s.memory||{}).some(info=>info.problem);
    if(hasProblem&&!memory.dataset.problem)$('session-details').open=true;
    memory.dataset.problem=hasProblem?'true':'';
    const stamp=JSON.stringify(s.memory);
    if(memory.dataset.stamp!==stamp){
      memory.dataset.stamp=stamp;
      memory.replaceChildren();
      for(const [store,info] of Object.entries(s.memory||{})){
        if(info.problem){
          const p=document.createElement('p');
          p.textContent=info.problem;
          memory.append(p);
        }
        if(info.generations.length){
          const label=document.createElement('label');
          label.textContent='Restore '+store+' memory ';
          const select=document.createElement('select');
          for(const generation of info.generations){
            const option=document.createElement('option');
            option.value=generation;
            option.textContent=new Date(Number(generation.split('-')[0])/1e6).toLocaleString();
            select.append(option);
          }
          const button=document.createElement('button');
          button.textContent='Restore saved generation';
          button.onclick=()=>command('recover_memory',{
            store,generation:select.value
          }).catch(failure);
          label.append(select,button);
          memory.append(label);
        }
      }
    }
    const box=$('messages'),bottom=box.scrollHeight-box.scrollTop-box.clientHeight<50;
    for(const m of s.messages){
      if(known.has(m.id))continue;
      known.add(m.id);
      const div=document.createElement('div');
      div.className='message '+m.role;
      const name=document.createElement('span');
      name.className='role';
      name.textContent=m.role==='user'?'You':'Companion';
      div.append(name,document.createTextNode(m.text));
      box.append(div);
    }
    if(bottom)box.scrollTop=box.scrollHeight;
  } catch(e){
    connectionError=e.message;
    $('error').textContent=connectionError;
  }
  setTimeout(refresh,400);
}
if(document.body.dataset.selected==='true'){
  $('game').value='minecraft';
}
refresh();
"""
