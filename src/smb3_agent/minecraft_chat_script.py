"""Served Minecraft chat behavior; kept as a Python asset for frozen packaging.

The HTML renderer and HTTP route import this constant without parsing a document.
Session credentials come from the escaped document dataset, never script text.
"""

CHAT_JS = r"""
const token=document.body.dataset.token, $=id=>document.getElementById(id);
let sid=null,url=null,shown=true,known=new Set(),sending=false,localError='',connectionError='';
$('draft').value=sessionStorage.getItem('minecraft-draft')||'';
$('design-mode').onchange=()=>{$('draft').maxLength=$('design-mode').checked?8000:2000;$('plan-guide').hidden=!$('design-mode').checked;};
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
  world:$('world').value,create:'true',accept_eula:String($('eula').checked),project:String($('build-enabled').checked)
}).catch(failure);
for(const [id,action] of [['project-prepare','project_prepare'],['project-run','project_run'],['project-undo','project_undo'],['project-undo-unmodified','project_undo_unmodified']])$(id).onclick=()=>command(action).catch(failure);
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
function viewerSource(){return url?url+($('view-mode').value==='inside'?'?view=inside':''):'about:blank';}
$('view-mode').onchange=()=>{$('view').src=shown?viewerSource():'about:blank';};
$('toggle').onclick=()=>{
  shown=!shown;
  $('live-panel').hidden=!shown;
  $('view').src=shown?viewerSource():'about:blank';
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
      text,request_id:crypto.randomUUID(),design:String($('design-mode').checked)
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

let designRevision=0,designKey='',terrainKey='',designComponents=[];
function svgNode(parent,tag,attrs){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));parent.append(n);return n;}
let architectureReview=0,initialDesignMode=false,architectureKey='',editorKey='';
function renderDesign(s){
  $('design-panel').hidden=!s.design;$('design-mode-label').hidden=!s.design;
  if(!s.design){$('design-mode').checked=false;return;}
  const d=s.design.current,locked=s.busy||s.stopping||s.connecting||s.project?.state==='running';
  const reviewReady=!d?.planning||d.planning.state==='ready';
  if(!initialDesignMode){initialDesignMode=true;$('design-mode').checked=!d;$('design-mode').onchange();}
  $('design-views').hidden=!d;$('design-measurements').hidden=!d;$('design-checklist').hidden=!d;
  $('project-next-step').textContent=!d?'Plan your project in the conversation.':locked?'Your companion is working. You can chat or press Stop.':!reviewReady?'Your plan needs attention. Check the notes below, then describe the change in Plan mode.':!s.project?.terrain?'Review the landscape before building.':s.project.terrain.progress?.verified_stages<s.project.terrain.stages_count?'Landscape reviewed. Start or continue when ready.':!s.project?.architecture?'Landscape ready. Choose a place and review its buildings.':'Review changes before continuing the buildings.';
  const previewComponents=new Set(s.design.preview_components||[]);
  const hasSample=previewComponents.size>0;
  $('design-prepare').disabled=locked||!d||!reviewReady||!hasSample;$('design-upload').disabled=locked;
  const bound=s.design.bound?.[0];
  $('design-build').disabled=locked||!reviewReady||!bound||bound.revision!==d?.revision||bound.build_revision!==s.project?.revision;
  $('design-save-edit').disabled=locked||!d;
  $('design-planning').hidden=!d?.planning||d.planning.state==='ready';
  $('design-planning').textContent=d?.planning?`${d.planning.state==='ready'?'Plan ready — review the design': 'Planning: '+d.planning.state}. ${(d.planning.issues||[]).join(' · ')}`:'';
  const terrain=s.project?.terrain;
  $('terrain-map').toggleAttribute('hidden',!terrain);$('terrain-details').hidden=!terrain;
  $('terrain-summary').textContent=terrain?`${terrain.progress.verified_stages??0} / ${terrain.stages_count} stages saved · ${terrain.progress.phase||'Reviewed'}. ${s.project.error||''}`:d?'Review the landscape to enable construction.':'Create a plan in chat to review the landscape.';
  const terrainGeometry=JSON.stringify([terrain?.design_revision,terrain?.preview]);
  if(terrainGeometry!==terrainKey){terrainKey=terrainGeometry;$('terrain-map').replaceChildren();
  if(terrain){$('terrain-map').setAttribute('viewBox',`0 0 ${terrain.extent} ${terrain.extent}`);for(const [x,z,h,wet] of terrain.preview){const r=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const [k,v] of Object.entries({x,y:z,width:8,height:8,fill:wet?'#477da6':`hsl(95 30% ${28+h}%)`}))r.setAttribute(k,String(v));$('terrain-map').append(r);}
    for(const [name,site] of Object.entries(terrain.reservations)){const [x,z,w,h]=site.box;svgNode($('terrain-map'),'rect',{x,y:z,width:w,height:h,fill:'none',stroke:'#fff','stroke-width':1});const label=svgNode($('terrain-map'),'text',{x,y:z+4,'font-size':4,fill:'#fff'});label.textContent=name;}
  }}
  $('terrain-review').disabled=locked||!reviewReady||!d;
  $('terrain-refresh').disabled=locked||!reviewReady||!terrain;
  $('terrain-run').disabled=locked||!reviewReady||terrain?.design_revision!==d?.revision;
  $('terrain-status').textContent=terrain?`${terrain.extent} × ${terrain.extent} blocks · ${terrain.cells.toLocaleString()} planned cells · 32-block protected outer buffer. ${terrain.review} Crests are positioned to preserve heights and clear entrances: ${terrain.peaks.map(p=>p.name+': '+p.height+' blocks above water').join('; ')}. ${terrain.progress.phase||'Reviewed'} · ${terrain.progress.verified_stages||0}/${terrain.stages_count} stages verified · ${terrain.progress.elapsed_seconds||0}s. Reserved sites in this landscape: ${Object.entries(terrain.reservations).map(([name,site])=>name+' at '+site.box[0]+', '+site.box[1]+'; elevation '+site.level).join(' · ')}. ${s.project.error||''}`:'Review terrain to inspect expanded bounds and stages. No terrain is built until you start.';
  const architecture=s.project?.architecture;
  architectureReview=architecture?.review||0;
  $('architecture-next').textContent=(!terrain||terrain.progress.verified_stages<terrain.stages_count)?'Review and complete the landscape first.':!architecture?'Choose a place and materials to review.':'Review applies to the saved plan and materials. Changes require a new review.';
  $('architecture-arrange').disabled=locked||!reviewReady;
  $('architecture-review').disabled=locked||!reviewReady||!terrain;
  $('architecture-run').disabled=locked||!architecture||architecture.design_revision!==d?.revision||architecture.unsupported.length>0||architecture.dependencies.length>0;
  const nextArchitectureKey=JSON.stringify([architecture,s.project?.error]);
  if(nextArchitectureKey!==architectureKey){architectureKey=nextArchitectureKey;
  const expanded=new Set([...$('architecture-status').querySelectorAll('details[open]')].map(n=>n.dataset.component));
  $('architecture-status').replaceChildren();
  if(architecture){
    const p=document.createElement('p');p.textContent=`${architecture.cells.toLocaleString()} planned cells · ${architecture.progress.phase||'reviewed'} · ${architecture.progress.elapsed_seconds||0}s. ${s.project.error||''}`;$('architecture-status').append(p);
    for(const c of architecture.components){const detail=document.createElement('details'),head=document.createElement('summary');detail.dataset.component=c.name;detail.open=expanded.has(c.name);head.textContent=c.name+' · '+(architecture.completed.includes(c.name)?'Saved completion':'Not completed');const p=document.createElement('p');p.textContent=`${c.name}: ${c.box[2]} × ${c.box[3]}, elevation ${c.box[4]}, height ${c.box[5]}, rotation ${c.turn*90}°, ${c.material}. Rooms: ${c.rooms.map(r=>r.name).join(', ')||'open space'}. Objects: ${c.objects.map(o=>o.type+' ('+o.capability+')'+(o.label?': '+o.label:'')).join(', ')||'none'}. ${(c.extensions||[]).map(e=>e.type+': '+e.width+' × '+e.depth+'. '+e.note).join(' ')} ${architecture.completed.includes(c.name)?'Saved completion; inspect again on continuation.':'Not completed.'}`;detail.append(head,p);$('architecture-status').append(detail);}
    for(const issue of [...architecture.dependencies,...architecture.unsupported]){const p=document.createElement('p');p.textContent='Needs review: '+issue;$('architecture-status').append(p);}
  }
  }
  designRevision=d?.revision||0;
  const key=JSON.stringify(s.design);if(key===designKey)return;designKey=key;
  $('design-summary').textContent=d?`${d.title} · ${d.extent} × ${d.extent} blocks · version ${d.revision}. ${d.uncertainty}`:'';
  for(const id of ['design-map','design-mass','design-components','design-palette','design-references','design-component','design-checklist-items'])$(id).replaceChildren();
  for(const ref of s.design.references){const card=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption');img.src='/api/minecraft/reference?id='+encodeURIComponent(ref.id);img.alt=ref.name;caption.textContent=ref.name+' — '+ref.caption;card.append(img,caption);$('design-references').append(card);}
  if(!d)return;
  designComponents=d.components;
  if(editorKey!==JSON.stringify(designComponents)){editorKey=JSON.stringify(designComponents);
  const selectedPlace=$('design-edit-name').value;$('design-edit-name').replaceChildren();
  for(const c of designComponents){const option=document.createElement('option');option.value=c.name;option.textContent=c.name;$('design-edit-name').append(option);}
  if(designComponents.some(c=>c.name===selectedPlace))$('design-edit-name').value=selectedPlace;
  loadDesignEditor();}
  for(const row of d.checklist||[]){const item=document.createElement('details'),head=document.createElement('summary'),facts=document.createElement('p'),quote=document.createElement('blockquote');head.textContent=`${row.name} · ${row.status}${row.issues.length?' · '+row.issues.join('; '):''}`;facts.textContent=`${Object.entries(row.constraints).map(([key,value])=>({kind:'Shape',width:'Width',depth:'Depth',height:'Height',elevation:'Elevation',turn:'Quarter turns',count:'Quantity',storeys:'Storeys',border:'Border width',zone:'Area'}[key]||key)+': '+value).join(' · ')}. Rooms: ${row.rooms.join(', ')||'none specified'}. Connections: ${row.connections.join(', ')||'none specified'}. Decorative assemblies: ${row.objects.join(', ')||'none specified'}. Native functions, still unverified: ${row.native.join(', ')||'none specified'}.`;quote.textContent=row.details;item.append(head,facts,quote);$('design-checklist-items').append(item);}
  const colors={terrain:'#9dbb8c',water:'#7eafc7',grove:'#6e9977',cave:'#92918b',path:'#d5c8a8',building:'#b38b67',tower:'#aa9484',bridge:'#b9a075',dock:'#b9a075',wreck:'#92775d',decoration:'#ceba98',pavilion:'#c99c70',platform:'#bfa27f'};
  for(const id of ['design-map','design-mass'])$(id).setAttribute('viewBox',`-35 -55 ${d.extent+70} ${d.extent+110}`);
  svgNode($('design-map'),'rect',{x:-32,y:-32,width:d.extent+64,height:d.extent+64,fill:'none',stroke:'#78927b','stroke-dasharray':'4 4'});
  svgNode($('design-map'),'rect',{x:0,y:0,width:d.extent,height:d.extent,fill:'none',stroke:'#50616b'});
  for(const old of d.previous_components||[]){if(d.changed.includes(old.name)){const [x,z,w,h]=old.box;svgNode($('design-map'),'rect',{x,y:z,width:w,height:h,fill:'none',stroke:'#8e5b97','stroke-dasharray':'2 2','stroke-width':1});}}
  const byName=new Map(d.components.map(c=>[c.name,c]));
  for(const c of d.components){const [x,z,w,depth,y,h]=c.box;
    for(const link of c.connections||[c.link]){if(link&&byName.has(link)){const b=byName.get(link).box;svgNode($('design-map'),'line',{x1:x+w/2,y1:z+depth/2,x2:b[0]+b[2]/2,y2:b[1]+b[3]/2,stroke:'#52654b','stroke-width':2});}}
    svgNode($('design-map'),'rect',{x,y:z,width:w,height:depth,fill:colors[c.kind],stroke:d.changed.includes(c.name)?'#1767bc':'#57666b','stroke-width':d.changed.includes(c.name)?2:0.6});
    const label=svgNode($('design-map'),'text',{x:x+1,y:z+5,'font-size':5});label.textContent=c.name;
    svgNode($('design-mass'),'rect',{x:x+z*.12,y:z-y-h,width:w,height:depth,fill:colors[c.kind],stroke:'#5b6267','stroke-width':.6});
    svgNode($('design-mass'),'path',{d:`M${x+z*.12},${z-y-h+depth} v${h} h${w} v${-h}`,fill:colors[c.kind],opacity:.6,stroke:'#5b6267','stroke-width':.5});
    const card=document.createElement('article');card.className='design-card'+(d.changed.includes(c.name)?' changed':'');
    const title=document.createElement('strong'),body=document.createElement('p');title.textContent=c.name;
    body.textContent=`${c.kind} · ${w} × ${depth}, elevation ${y}, height ${h}, turn ${c.turn*90}°. ${c.detail} ${c.rooms?.length?'Rooms: '+c.rooms.join(', ')+'. ':''}${c.constraints?.count?'Quantity: '+c.constraints.count+'. ':''}${c.link?'Connects to '+c.link+'. ':''}${c.link&&!byName.has(c.link)?'Connection unresolved. ':''}${previewComponents.has(c.name)?'Bounded preview supported; native functions not included.':(['terrain','water','grove','cave','path'].includes(c.kind)?'Included in the separately reviewed terrain manifest.':'Use architecture review to inspect build support, dependencies and completion. Decorative machinery cannot function.')}`;
    card.append(title,body);$('design-components').append(card);
    if(previewComponents.has(c.name)){const opt=document.createElement('option');opt.value=c.name;opt.textContent=c.name;$('design-component').append(opt);}
  }
  const previousArchitecture=$('architecture-component').value;$('architecture-component').replaceChildren(new Option('All supported places',''));for(const c of d.components){if(['building','pavilion','platform','tower','dock','wreck','decoration'].includes(c.kind)||(c.objects||[]).length)$('architecture-component').append(new Option(c.name,c.name));}$('architecture-component').value=previousArchitecture;
  const palettes={warm:['Oak','Pale fabric','Stone'],coastal:['Oak','Glass','Pale fabric'],natural:['Spruce','Stone','Glass'],industrial:['Stone brick','Glass','Spruce']};
  for(const name of palettes[d.palette]||[]){const chip=document.createElement('span');chip.textContent=name;$('design-palette').append(chip);}
  $('design-estimate').textContent=`${d.estimated_volume.toLocaleString()} blocks of bounding volume. ${d.estimate_note} Dashed border: ${d.protected_buffer}-block no-write buffer. Blue outlines: latest changes; purple dashes: prior footprints. Connections are planned, not verified walkable routes.`;
}
function loadDesignEditor(){const c=designComponents.find(c=>c.name===$('design-edit-name').value);if(!c)return;$('design-edit-kind').value=c.kind;['width','depth','height'].forEach((k,i)=>$('design-'+k).value=c.size[i]);$('design-zone').value=c.zone;$('design-level').value=c.level;$('design-turn').value=c.turn;}
$('design-edit-name').onchange=loadDesignEditor;
$('design-save-edit').onclick=()=>command('design_edit',{design_revision:String(designRevision),component:$('design-edit-name').value,kind:$('design-edit-kind').value,size:JSON.stringify(['width','depth','height'].map(k=>Number($('design-'+k).value))),zone:$('design-zone').value,level:$('design-level').value,turn:$('design-turn').value}).catch(failure);
$('architecture-arrange').onclick=()=>command('architecture_arrange',{design_revision:String(designRevision)}).catch(failure);
$('architecture-review').onclick=()=>command('architecture_review',{design_revision:String(designRevision),component:$('architecture-component').value,material:$('architecture-material').value}).catch(failure);
$('architecture-run').onclick=()=>command('architecture_run',{design_revision:String(designRevision),architecture_review:String(architectureReview)}).catch(failure);
$('terrain-refresh').onclick=()=>command('terrain_refresh',{design_revision:String(designRevision)}).catch(failure);
$('terrain-review').onclick=()=>command('terrain_review',{design_revision:String(designRevision)}).catch(failure);
$('terrain-run').onclick=()=>command('terrain_run',{design_revision:String(designRevision)}).catch(failure);
$('design-prepare').onclick=()=>command('design_prepare',{design_revision:String(designRevision),component:$('design-component').value}).catch(failure);
$('design-build').onclick=()=>command('design_run',{design_revision:String(designRevision),component:$('design-component').value}).catch(failure);
$('design-upload').onclick=async()=>{try{
  const file=$('design-file').files[0];if(!file||file.size>4000000||!['image/png','image/jpeg'].includes(file.type))throw Error('Select a PNG or JPEG no larger than 4 MB.');
  const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});
  const response=await fetch('/api/minecraft/reference',{method:'POST',body:new URLSearchParams({csrf_token:token,session_id:sid||'',name:file.name,caption:$('design-caption').value,image:data})});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Reference could not be saved');
  $('design-file').value='';$('design-caption').value='';
}catch(e){failure(e);}};

function renderMessages(messages,box){
  const current=messages.slice(-500),retained=new Set(current.map(m=>m.id));
  for(const node of [...box.children]){
    if(node.dataset.messageId&&!retained.has(node.dataset.messageId)){known.delete(node.dataset.messageId);node.remove();}
  }
  for(const m of current){
    if(known.has(m.id))continue;
    known.add(m.id);
    const div=document.createElement('div');
    div.dataset.messageId=m.id;
    div.className='message '+m.role;
    const name=document.createElement('span');
    name.className='role';
    name.textContent=m.role==='user'?'You':'Companion';
    div.append(name,document.createTextNode(m.text));
    box.append(div);
  }
}

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
    $('open-world').hidden=!!w&&!w.exists;
    $('setup-title').textContent=w&&!w.exists?'Create your world':'Open your world';
    $('setup-panel').dataset.new=String(!!w&&!w.exists);
    $('new-world-title').textContent=w&&!w.exists?'World settings':'Create a new practice world';
    const setupChoice=$('world').value+':'+String(w?.exists);
    if(w&&$('new-world').dataset.choice!==setupChoice){$('new-world').dataset.choice=setupChoice;$('new-world').open=!w.exists;}
    $('create-world').disabled=s.connecting||!!sid||w?.exists;
    $('setup-panel').hidden=!!state.ready;
    document.body.dataset.connected=String(!!state.ready);
    $('live-panel').hidden=!shown||(!sid&&!s.connecting);
    $('session-tools').hidden=!sid&&!s.connecting&&!s.error&&!s.connection_fault;
    $('toggle').disabled=!state.viewer_url;
    $('activity-panel').hidden=!sid&&!s.connecting;
    $('get-java').hidden=!!setup.java?.ready;
    $('setup-links').hidden=!!setup.java?.ready;
    $('setup-status').textContent=[!setup.node?.ready?setup.node?.message:null,!setup.java?.ready?setup.java?.message:null,w?.ready?'Your saved world is ready.':w?.message].filter(Boolean).join(' · ');
    $('empty-chat').hidden=s.messages.length>0;
    $('empty-chat').lastChild.textContent=state.ready?'Ask a question or give your companion a goal.':'Open a world to explore, gather or build together.';
    $('connection').textContent=s.connecting?'Connecting…':state.ready?'Connected':'Disconnected';
    $('identity').textContent=state.ready&&state.character?state.character+' · '+(state.game_mode||'Practice')+' world':'Minecraft';
    $('project-tools').hidden=!s.project;
    renderDesign(s);
    for(const id of ['project-prepare','project-run','project-undo','project-undo-unmodified'])$(id).disabled=s.project?.state==='running'||s.stopping||s.connecting;
    $('activity').textContent=s.busy?s.activity:s.project?'Project: '+s.project.state+(s.project.error?' · '+s.project.error:''):s.activity;
    $('progress').textContent=s.progress||'';
    $('goal').textContent=s.goal?s.goal:'';
    $('ai').textContent=s.ai.message;
    $('ai-privacy').textContent=s.ai.inference||'';
    $('pending').textContent=s.stopping?'Stopping · draft retained; send after confirmation':s.stop_failed?'Stop unconfirmed · reconnect before sending':s.busy?(state.active||s.goal?'Thinking · current task continues':'Thinking…'):'';
    $('send').disabled=!s.ai.available||s.busy||s.stopping||s.stop_failed||!state.ready||s.connecting;
    $('reconnect').disabled=s.connecting;
    $('send-status').textContent=s.stopping?'Wait for Stop to finish.':s.stop_failed?'Reconnect to continue.':s.connecting?'Connecting to your world…':!state.ready?'Open a world to send a message.':!s.ai.available?'Check AI setup before sending.':s.busy?'You can keep editing your draft.':'';
    connectionError='';
    $('error').textContent=[...new Set([localError,s.error].filter(Boolean))].join('\n');
    if(state.viewer_url!==url){
      url=state.viewer_url;
      if(shown)$('view').src=viewerSource();
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
    renderMessages(s.messages,box);
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
