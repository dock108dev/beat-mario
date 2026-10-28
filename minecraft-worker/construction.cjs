'use strict'
const {Vec3}=require('vec3')
const {inside,safeTarget,stands,visibleFrom,multiChanges}=require('./resource-skills.cjs')
const {counts,SUPPORTED}=require('./crafting.cjs')
const AIR=['air','cave_air','void_air']
const point=p=>new Vec3(p.x,p.y,p.z)
function cellsOf(args) {
  if(!Array.isArray(args.cells)||!args.cells.length||args.cells.length>256) throw Error('invalid_structure_cells')
  return args.cells.map(c=>{if(!c.position||!['x','y','z'].every(k=>Number.isInteger(c.position[k]))||!SUPPORTED.includes(c.item)||(!c.item.endsWith('_planks')&&c.item!=='crafting_table')) throw Error('invalid_structure_cell'); return c})
}
function inspect(bot,args,regions) {
  const cells=cellsOf(args), occupied=[], unsupported=[], protectedCells=[], unknown=[]
  const intended=new Set(cells.map(c=>JSON.stringify(c.position)))
  const removals=args.removable||[]
  if(!Array.isArray(removals)||removals.length>192)throw Error('invalid_removal_plan')
  const willRemove=(p,name)=>removals.some(c=>c.item===name&&['x','y','z'].every(k=>c.position[k]===p[k]))
  if(args.avoid && (!Array.isArray(args.avoid)||args.avoid.length>4096)) throw Error('invalid_avoidance')
  const avoided=new Set((args.avoid||[]).map(c=>`${c.position.x},${c.position.z}`))
  for(const c of cells)if(avoided.has(`${c.position.x},${c.position.z}`))protectedCells.push(c)
  for(const c of cells) {
    const p=point(c.position); if(p.distanceTo(bot.entity.position)>32) throw Error('site_out_of_bounds')
    const b=bot.blockAt(p),below=bot.blockAt(p.offset(0,-1,0))
    if(inside(p,regions)) protectedCells.push(c)
    if(!b||!below) {unknown.push(c); continue}
    if(!AIR.includes(b.name) && b.name!==c.item && !willRemove(p,b.name)) occupied.push({...c,actual:b.name})
    if(!below || (below.boundingBox!=='block' && !intended.has(JSON.stringify({x:p.x,y:p.y-1,z:p.z})))) unsupported.push(c)
  }
  const bounds={minX:Math.min(...cells.map(c=>c.position.x)),maxX:Math.max(...cells.map(c=>c.position.x)),minY:Math.min(...cells.map(c=>c.position.y)),maxY:Math.max(...cells.map(c=>c.position.y)),minZ:Math.min(...cells.map(c=>c.position.z)),maxZ:Math.max(...cells.map(c=>c.position.z))}
  if(args.clearance) {
    if((bounds.maxX-bounds.minX+1)*(bounds.maxY-bounds.minY+1)*(bounds.maxZ-bounds.minZ+1)>256) throw Error('clearance_budget')
    for(let x=bounds.minX;x<=bounds.maxX;x++)for(let y=bounds.minY;y<=bounds.maxY;y++)for(let z=bounds.minZ;z<=bounds.maxZ;z++) {
      const position={x,y,z},b=bot.blockAt(point(position))
      if(intended.has(JSON.stringify(position))) continue
      if(!b)unknown.push({position})
      else if(!AIR.includes(b.name) && !willRemove(position,b.name)) {
        const doorwayAdjacent = [new Vec3(1,0,0),new Vec3(-1,0,0),new Vec3(0,0,1),new Vec3(0,0,-1)].some(d=>{
          const q=point(position).plus(d)
          return (q.x===bounds.minX||q.x===bounds.maxX||q.z===bounds.minZ||q.z===bounds.maxZ) && q.x>=bounds.minX&&q.x<=bounds.maxX&&q.z>=bounds.minZ&&q.z<=bounds.maxZ&&!intended.has(JSON.stringify({x:q.x,y:bounds.minY,z:q.z}))
        })
        const furniture=!doorwayAdjacent && b.name==='crafting_table' && y===bounds.minY && x>bounds.minX && x<bounds.maxX && z>bounds.minZ && z<bounds.maxZ && (bounds.maxX-bounds.minX-1)*(bounds.maxZ-bounds.minZ-1)>=4
        if(!furniture)occupied.push({position,actual:b.name,clearance:true})
      }
      if(inside(position,regions))protectedCells.push({position})
      if(y===bounds.minY && bot.blockAt(point(position).offset(0,-1,0))?.boundingBox!=='block')unsupported.push({position})
    }
  }
  // A doorway needs an exterior standing cell too: adjacent saved buildings
  // must not trap the bot after the walls close.
  if(args.clearance) {
    for(let x=bounds.minX;x<=bounds.maxX;x++)for(let z=bounds.minZ;z<=bounds.maxZ;z++) {
      const y=bounds.minY, p={x,y,z}
      if(intended.has(JSON.stringify(p)) || intended.has(JSON.stringify({x,y:y+1,z})))continue
      const dirs=[]
      if(x===bounds.minX)dirs.push([-1,0]);if(x===bounds.maxX)dirs.push([1,0])
      if(z===bounds.minZ)dirs.push([0,-1]);if(z===bounds.maxZ)dirs.push([0,1])
      for(const [dx,dz] of dirs) {
        const exit={x:x+dx,y,z:z+dz}
        for(const dy of [0,1]) {
          const q={...exit,y:y+dy}, b=bot.blockAt(point(q))
          if(!b)unknown.push({position:q,access:true})
          else if(!AIR.includes(b.name))occupied.push({position:q,actual:b.name,access:true})
          if(inside(q,regions))protectedCells.push({position:q,access:true})
        }
        if(bot.blockAt(point(exit).offset(0,-1,0))?.boundingBox!=='block')unsupported.push({position:exit,access:true})
      }
    }
  }
  const inaccessible=[]
  if(args.clearance && !occupied.length && !unknown.length) {
    const standing=[]
    for(let x=bounds.minX-2;x<=bounds.maxX+2;x++)for(let z=bounds.minZ-2;z<=bounds.maxZ+2;z++) {
      const p=new Vec3(x,bounds.minY,z)
      if(intended.has(JSON.stringify({x,y:p.y,z}))||intended.has(JSON.stringify({x,y:p.y+1,z})))continue
      if(bot.blockAt(p.offset(0,-1,0))?.boundingBox==='block' && AIR.includes(bot.blockAt(p)?.name) && AIR.includes(bot.blockAt(p.offset(0,1,0))?.name) && !inside(p,regions))standing.push(p.offset(.5,1.62,.5))
    }
    for(const c of cells)if(!standing.some(p=>p.distanceTo(point(c.position).offset(.5,.5,.5))<=4.5))inaccessible.push(c)
  }
  return {observed:'site',inaccessible,occupied,unsupported,protected:protectedCells,unknown,cells:cells.map(c=>({...c,actual:bot.blockAt(point(c.position))?.name||null}))}
}
function fingerprint(bot,cells,regions,avoid) {
 const xs=cells.map(c=>c.position.x),ys=cells.map(c=>c.position.y),zs=cells.map(c=>c.position.z), states=[]
 for(let x=Math.min(...xs)-2;x<=Math.max(...xs)+2;x++)for(let z=Math.min(...zs)-2;z<=Math.max(...zs)+2;z++)for(let y=Math.min(...ys)-1;y<=Math.max(...ys)+1;y++)states.push(bot.blockAt(new Vec3(x,y,z))?.stateId??bot.blockAt(new Vec3(x,y,z))?.name??'unknown')
 return require('node:crypto').createHash('sha256').update(JSON.stringify([states,regions,avoid,cells])).digest('hex')
}
function reachableAccess(bot,cells,args,regions) {
 const floor=Math.min(...cells.map(c=>c.position.y)), minX=Math.min(...cells.map(c=>c.position.x)),maxX=Math.max(...cells.map(c=>c.position.x)),minZ=Math.min(...cells.map(c=>c.position.z)),maxZ=Math.max(...cells.map(c=>c.position.z))
 const intended=new Set(cells.map(c=>`${c.position.x},${c.position.y},${c.position.z}`)), available=[]
 for(let x=minX-1;x<=maxX+1;x++)for(let z=minZ-1;z<=maxZ+1;z++) {
  const p=new Vec3(x,floor,z)
  if(intended.has(`${x},${floor},${z}`)||intended.has(`${x},${floor+1},${z}`)||inside(p,regions))continue
  if(bot.blockAt(p.offset(0,-1,0))?.boundingBox!=='block'||!AIR.includes(bot.blockAt(p)?.name)||!AIR.includes(bot.blockAt(p.offset(0,1,0))?.name))continue
  const route=require('./routes.cjs').route(bot,bot.entity.position,p,{...args,exact_target:true})
  if(route.known)available.push({position:p,route_length:route.length})
  if(available.length>=12)break
 }
 const uncovered=cells.filter(c=>!available.some(s=>point(s.position).offset(.5,1.62,.5).distanceTo(point(c.position).offset(.5,.5,.5))<=4.5))
 return {known:available.length>0&&!uncovered.length,standing:available,uncovered:uncovered.length}
}
function survey(bot,args,regions) {
 const cells=cellsOf(args),floor=Math.min(...cells.map(c=>c.position.y)),width=Math.max(...cells.map(c=>c.position.x))-Math.min(...cells.map(c=>c.position.x))+1,depth=Math.max(...cells.map(c=>c.position.z))-Math.min(...cells.map(c=>c.position.z))+1
 const offsets=[{x:0,z:0}]
 for(let radius of (args.offer_only?[6,12,20]:[4,8,12]))for(let i=0;i<8;i++)offsets.push({x:Math.round(radius*Math.cos(i*Math.PI/4)),z:Math.round(radius*Math.sin(i*Math.PI/4))})
 const rejected=[],history=args.rejections||[];let inspected=0,reused=0
 for(const o of offsets) {
  // Observe actual local support elevation; don't assume the bot's height fits terrain.
  const originX=cells[0].position.x+o.x,originZ=cells[0].position.z+o.z
  const heights=[0,1,-1,2,-2,3,-3,4,-4].filter(dy=>bot.blockAt(new Vec3(originX,floor+dy-1,originZ))?.boundingBox==='block').slice(0,3)
  for(const y of heights) {
   const shifted=cells.map(c=>({item:c.item,position:{x:c.position.x+o.x,y:c.position.y+y,z:c.position.z+o.z}}))
   const origin={x:Math.min(...shifted.map(c=>c.position.x)),y:floor+y,z:Math.min(...shifted.map(c=>c.position.z))}
   const signature=fingerprint(bot,shifted,regions,args.avoid)
   const prior=history.find(r=>r.signature===signature && Date.now()-r.at_ms<300000)
   if(prior){rejected.push({...prior,reused:true});reused++;continue}
   inspected++
   let result
   try {
    if(args.goal_origin&&shifted.some(c=>point(c.position).distanceTo(point(args.goal_origin))>32))throw Error('outside_goal_bounds')
    result=inspect(bot,{cells:shifted,clearance:true,avoid:args.avoid},regions)
   }catch(e){rejected.push({origin,signature,reasons:{bounds:e.message}});continue}
   const reasons={occupied:result.occupied.length,protected:result.protected.length,unknown:result.unknown.length,placement_access:result.inaccessible.length,foundation:result.unsupported.filter(c=>c.position.y===floor+y).length}
   let access=null
   if(!Object.values(reasons).some(Boolean)) {
    access=reachableAccess(bot,shifted,args,regions)
    if(!access.known)reasons.route_access=1
    else return {...result,translation:{x:o.x,y,z:o.z},rejected,inspected,reused,access,origin,width,depth}
   }
   rejected.push({origin,signature,reasons})
  }
 }
 return {observed:'site_search_exhausted',rejected,inspected,reused}
}
function collision(bot,p) {
  return Object.values(bot.entities).some(e=>e.position && e.name!=='item' && Math.abs(e.position.x-(p.x+.5))<.8 && Math.abs(e.position.z-(p.z+.5))<.8 && e.position.y<p.y+1 && e.position.y+(e.height||1.8)>p.y)
}
function support(bot,p) {
  for(const d of [new Vec3(0,-1,0),new Vec3(-1,0,0),new Vec3(1,0,0),new Vec3(0,0,-1),new Vec3(0,0,1)]) {
    const b=bot.blockAt(p.plus(d)); if(b?.boundingBox==='block' && !['crafting_table','chest','furnace'].includes(b.name)) return {block:b,face:d.scaled(-1)}
  }
  return null
}
async function place(bot,args,signal,regions,goals) {
  cellsOf({cells:[{position:args.target,item:args.item}]})
  const p=point(args.target); safeTarget(bot,p,regions)
  let block=bot.blockAt(p)
  if(block?.name===args.item) return {observed:'already_present',position:p,item:args.item,consumed:0}
  if(!block||!AIR.includes(block.name)) throw Error('occupied_cell_removal_permission_required')
  let ref=support(bot,p); if(!ref) throw Error('missing_placement_support')
  if(!visibleFrom(bot,bot.entity.position,ref.block.position) || collision(bot,p)) {
    let reached=false
    for(const stand of stands(bot,ref.block.position,regions,1).sort((a,b)=>Math.abs(a.y-bot.entity.position.y)-Math.abs(b.y-bot.entity.position.y)).filter(s=>s.distanceTo(p)>.99 && (!args.goal_origin||s.distanceTo(point(args.goal_origin))<=32)).slice(0,3)) {
      signal.throwIfAborted()
      try {const timer=setTimeout(()=>bot.pathfinder.setGoal(null),3500); try {await bot.pathfinder.goto(new goals.GoalBlock(Math.floor(stand.x),Math.floor(stand.y),Math.floor(stand.z)))}finally{clearTimeout(timer)}; if(visibleFrom(bot,bot.entity.position,ref.block.position)&&!collision(bot,p)){reached=true;break}} catch(e){signal.throwIfAborted()}
    }
    if(!reached) throw Error('placement_face_unreachable')
  }
  signal.throwIfAborted(); safeTarget(bot,p,regions)
  block=bot.blockAt(p); ref=support(bot,p)
  if(!block||!AIR.includes(block.name)||!ref||collision(bot,p)||!visibleFrom(bot,bot.entity.position,ref.block.position)) throw Error('placement_site_changed')
  const item=bot.inventory.items().find(i=>i.name===args.item); if(!item) throw Error('material_shortfall')
  const before=counts(bot); let serverState=null
  const changed=pkt=>{if(pkt.location.x===p.x&&pkt.location.y===p.y&&pkt.location.z===p.z)serverState=pkt.type}
  const multi=pkt=>multiChanges(pkt).forEach(changed)
  bot._client.on('block_change',changed);bot._client.on('multi_block_change',multi)
  try {
    await bot.equip(item,'hand');signal.throwIfAborted()
    await bot.placeBlock(ref.block,ref.face);signal.throwIfAborted()
    const deadline=Date.now()+2500
    while(Date.now()<deadline && (serverState===null||bot.blockAt(p)?.name!==args.item||(bot.game.gameMode!=='creative'&&(counts(bot)[args.item]||0)!==before[args.item]-1))) {await new Promise(r=>setTimeout(r,25));signal.throwIfAborted()}
    if(serverState===null||bot.blockAt(p)?.stateId!==serverState||bot.blockAt(p)?.name!==args.item) throw Error('server_placement_not_verified')
    const consumed=before[args.item]-(counts(bot)[args.item]||0)
    if(bot.game.gameMode!=='creative'&&consumed!==1) throw Error('placement_consumption_not_verified')
    return {observed:'server_placement',position:p,item:args.item,consumed,server_state_id:serverState}
  }finally{bot._client.removeListener('block_change',changed);bot._client.removeListener('multi_block_change',multi)}
}
module.exports={fingerprint,reachableAccess,survey,cellsOf,inspect,place,collision,support}
