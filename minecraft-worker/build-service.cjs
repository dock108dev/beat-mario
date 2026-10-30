'use strict'
// Typed construction operations only. The existing worker Scheduler owns execution.
const { Vec3 } = require('vec3')
const BLOCKS = new Set(['air','stone','dirt','grass_block','sand','water','oak_planks','spruce_planks','oak_log','glass','oak_stairs','stone_bricks','oak_slab','oak_fence','torch','oak_door','chest','crafting_table','white_wool','oak_leaves','white_bed','glowstone','furnace'])
const key = p => `${p.x},${p.y},${p.z}`
function inside(p,b) { return ['x','y','z'].every(k=>Number.isInteger(p[k])&&p[k]>=b.min[k]&&p[k]<=b.max[k]) }
function check(p,region) {
  if (!region || !inside(p,region.bounds) || region.protected.some(b=>inside(p,b))) throw Error('build_region_or_protection')
}
function state(block) {
  if (!block) throw Error('build_chunk_unavailable')
  const properties=Object.entries(block.getProperties()).sort(([a],[b])=>a.localeCompare(b))
  return block.name+(properties.length?'['+properties.map(([k,v])=>`${k}=${v}`).join(',')+']':'')
}
const stateCaches=new WeakMap()
function allowed(value,registry) {
  if (typeof value!=='string'||value.length>256||!/^\w+(\[\w+=\w+(,\w+=\w+)*\])?$/.test(value)) throw Error('invalid_build_state')
  const name=value.split('[')[0]
  if (!BLOCKS.has(name)||!registry.blocksByName[name]) throw Error('unsupported_build_state')
  // Resolve the complete canonical state, including orientations, against the game registry.
  let cache=stateCaches.get(registry)
  if(!cache){cache={Block:require('prismarine-block')(registry),states:new Map()};stateCaches.set(registry,cache)}
  if(cache.states.has(value))return cache.states.get(value)
  const spec=registry.blocksByName[name]
  for(let id=spec.minStateId;id<=spec.maxStateId;id++)if(state(cache.Block.fromStateId(id,0))===value){
    if(cache.states.size>=512)cache.states.clear()
    cache.states.set(value,id);return id
  }
  throw Error('unknown_build_properties')
}
function inspect(bot,positions,region) {
  if (!Array.isArray(positions)||positions.length<1||positions.length>256)throw Error('build_inspection_bound')
  return positions.map(p=>{if(!region||!inside(p,region.observation_bounds||region.bounds))throw Error('inspection_out_of_region'); const b=bot.blockAt(new Vec3(p.x,p.y,p.z));return {position:p,state:state(b),state_id:b.stateId}})
}
async function apply(bot,args,signal,region,emit) {
  if(bot.game.gameMode!=='creative')throw Error('creative_build_mode_required')
  const cells=args.cells
  if(!Array.isArray(cells)||!cells.length||cells.length>64||new Set(cells.map(c=>key(c.position))).size!==cells.length)throw Error('build_batch_bound')
  const current=inspect(bot,cells.map(c=>c.position),region)
  for(let i=0;i<cells.length;i++) {
    check(cells[i].position,region);allowed(cells[i].before,bot.registry);allowed(cells[i].after,bot.registry)
    if(current[i].state!==cells[i].before)throw Error('build_precondition_conflict')
    if(['chest','oak_door','white_bed','furnace'].includes(cells[i].before.split('[')[0])&&cells[i].before!==cells[i].after)throw Error('interactive_block_removal_not_supported')
    const p=cells[i].position,e=bot.entity.position
    if(cells[i].after!=='air'&&Math.abs(p.x-e.x)<1&&Math.abs(p.z-e.z)<1&&Math.abs(p.y-e.y)<2)throw Error('build_player_collision')
    for(const player of Object.values(bot.players))if(player.entity&&player.username!==bot.username&&player.entity.position.distanceTo(new Vec3(p.x,p.y,p.z))<2)throw Error('build_player_collision')
  }
  signal.throwIfAborted()
  const nonce=require('node:crypto').randomUUID().replaceAll('-','')
  let receipt=false
  const message=m=>{if(m.toString().includes('GC_BUILD_'+nonce))receipt=true}
  bot.on('message',message)
  try {
    emit('build_command',null,{operation:{nonce,cells,mode:args.mode||'batch'}})
    // Even after cancellation, await the in-flight server barrier before releasing scheduler.
    const end=Date.now()+1200
    while(!receipt&&Date.now()<end)await new Promise(r=>setTimeout(r,10))
    if(!receipt)throw Error('build_server_barrier_unconfirmed')
    let observed=inspect(bot,cells.map(c=>c.position),region)
    const settle=Date.now()+900
    while(observed.some((c,i)=>c.state!==cells[i].after)&&Date.now()<settle){
      await new Promise(r=>setTimeout(r,10));observed=inspect(bot,cells.map(c=>c.position),region)
    }
    if(observed.some((c,i)=>c.state!==cells[i].after))throw Error('build_verification_conflict')
    emit('build_settled',null,{nonce,verified_at_ms:Date.now(),cells:cells.length})
    signal.throwIfAborted()
    return {observed:'verified_build_batch',cells:observed,verified_at_ms:Date.now()}
  }finally{bot.removeListener('message',message)}
}
module.exports={BLOCKS,inside,check,state,allowed,inspect,apply}

async function probe(bot,args,signal,region,emit) {
  check(args.target,region)
  const block=bot.blockAt(new Vec3(args.target.x,args.target.y,args.target.z))
  if(!block||bot.entity.position.distanceTo(block.position)>4.5)throw Error('probe_not_reachable')
  signal.throwIfAborted()
  if(block.name==='chest') {
    const window=await bot.openContainer(block)
    try {
      signal.throwIfAborted()
      const item=bot.inventory.items().find(i=>i.name==='oak_planks')
      if(!item)throw Error('probe_item_missing')
      const contents=()=>JSON.stringify(window.containerItems().map(i=>({name:i.name,count:i.count,nbt:i.nbt})))
      const initialContents=contents()
      const before=window.containerItems().filter(i=>i.type===item.type).reduce((n,i)=>n+i.count,0)
      await window.deposit(item.type,null,1)
      const after=window.containerItems().filter(i=>i.type===item.type).reduce((n,i)=>n+i.count,0)
      if(after!==before+1)throw Error('container_storage_not_observed')
      await window.withdraw(item.type,null,1)
      const restored=window.containerItems().filter(i=>i.type===item.type).reduce((n,i)=>n+i.count,0)
      if(restored!==before||contents()!==initialContents)throw Error('container_restore_unconfirmed')
      return {observed:'container_deposit_withdraw',before,after,preserved_contents:JSON.parse(initialContents)}
    }finally{window.close()}
  }
  if(block.name==='furnace') {
    const window=await bot.openFurnace(block)
    try {
      if(window.inputItem()||window.fuelItem()||window.outputItem())throw Error('probe_requires_empty_furnace')
      const potato=bot.registry.itemsByName.potato, fuel=bot.registry.itemsByName.oak_planks
      const output=bot.registry.itemsByName.baked_potato
      const count=()=>window.slots.slice(window.inventoryStart,window.inventoryEnd).filter(i=>i&&i.type===output.id).reduce((n,i)=>n+i.count,0)
      const before=count()
      signal.throwIfAborted()
      await window.putInput(potato.id,null,1)
      signal.throwIfAborted()
      await window.putFuel(fuel.id,null,1)
      const end=Date.now()+20000
      while(!window.outputItem()&&Date.now()<end){signal.throwIfAborted();await new Promise(r=>setTimeout(r,50))}
      if(window.outputItem()?.type!==output.id)throw Error('cooking_output_unconfirmed')
      await window.takeOutput()
      await bot._syncWindow(window)
      while(bot.blockAt(block.position).getProperties().lit&&Date.now()<end){signal.throwIfAborted();await new Promise(r=>setTimeout(r,50))}
      if(count()!==before+1||bot.blockAt(block.position).getProperties().lit)throw Error('cooking_completion_unconfirmed')
      return {observed:'native_cooking',item:'baked_potato',before,after:count()}
    }finally{window.close()}
  }
  if(block.name==='white_bed') {
    await bot.sleep(block)
    try {
      signal.throwIfAborted()
      if(!bot.isSleeping)throw Error('bed_sleep_unconfirmed')
      return {observed:'bed_sleep_and_wake'}
    }finally{if(bot.isSleeping)await bot.wake()}
  }
  if(block.name==='crafting_table') {
    const item=bot.registry.itemsByName.chest
    const count=()=>bot.inventory.items().filter(i=>i.type===item.id).reduce((n,i)=>n+i.count,0)
    const recipes=bot.recipesFor(item.id,null,1,block)
    if(!recipes.length)throw Error('probe_crafting_ingredients_missing')
    const before=count()
    await bot.craft(recipes[0],1,block)
    signal.throwIfAborted()
    if(count()!==before+1)throw Error('crafting_output_unconfirmed')
    return {observed:'table_recipe_crafted',item:'chest',before,after:count()}
  }
  if(block.name==='glowstone') {
    const position=[[0,1,0],[1,0,0],[-1,0,0],[0,0,1],[0,0,-1]].map(([x,y,z])=>block.position.offset(x,y,z)).find(p=>bot.blockAt(p)?.name==='air')
    if(!position)throw Error('light_probe_requires_adjacent_air')
    check(position,region)
    const nonce=require('node:crypto').randomUUID().replaceAll('-','')
    let lit=false,barrier=false
    const listener=m=>{const text=m.toString();if(text.includes('GC_LIGHT_'+nonce))lit=true;if(text.includes('GC_BUILD_'+nonce))barrier=true}
    bot.on('message',listener)
    try {
      emit('build_command',null,{operation:{mode:'light',position,nonce}})
      const end=Date.now()+1500
      while(!barrier&&Date.now()<end)await new Promise(r=>setTimeout(r,10))
      signal.throwIfAborted()
      if(!barrier||!lit)throw Error('server_illumination_unconfirmed')
      return {observed:'server_light_at_least_14',position}
    }finally{bot.removeListener('message',listener)}
  }
  if(block.name==='oak_door') {
    const before=state(block)
    if(args.keep_closed===true){
      if(block.getProperties().open===true)await bot.activateBlock(block)
      const end=Date.now()+1000
      while(bot.blockAt(block.position).getProperties().open!==false&&Date.now()<end)await new Promise(r=>setTimeout(r,20))
      if(bot.blockAt(block.position).getProperties().open!==false)throw Error('door_close_unconfirmed')
      return {observed:'door_closed'}
    }
    if(args.keep_open===true && block.getProperties().open===true)return {observed:'door_opened',state:before}
    await bot.activateBlock(block)
    const end=Date.now()+1000
    while(state(bot.blockAt(block.position))===before&&Date.now()<end)await new Promise(r=>setTimeout(r,20))
    if(state(bot.blockAt(block.position))===before)throw Error('door_did_not_toggle')
    if(args.keep_open===true){
      const opened=bot.blockAt(block.position)
      if(opened.getProperties().open!==true)throw Error('door_open_not_observed')
      return {observed:'door_opened',state:state(opened)}
    }
    await bot.activateBlock(bot.blockAt(block.position))
    const restore=Date.now()+1000
    while(state(bot.blockAt(block.position))!==before&&Date.now()<restore)await new Promise(r=>setTimeout(r,20))
    if(state(bot.blockAt(block.position))!==before)throw Error('door_restore_unconfirmed')
    return {observed:'door_toggle_and_restore'}
  }
  throw Error('unsupported_function_probe')
}
module.exports.probe=probe

function clearDoor(b) {
  return b?.name==='oak_door'&&b.getProperties().open===true&&b.shapes.every(s=>!(s[0]<.8&&s[3]>.2&&s[2]<.8&&s[5]>.2))
}
function doorWaypoints(bot, result) {
  for(const point of result.path || []) {
    const b=bot.blockAt(new Vec3(Math.floor(point.x),Math.floor(point.y),Math.floor(point.z)))
    if(clearDoor(b)) {
      // Pathfinder's generic shape-top postprocessor puts a waypoint on the door
      // leaf. Use the clear doorway center at its lower-half floor instead.
      point.x=b.position.x+.5;point.z=b.position.z+.5
      point.y=b.position.y-(b.getProperties().half==='upper'?1:0)
    }
  }
}
function configureMovements(movements,bot) {
  const getBlock=movements.getBlock.bind(movements)
  movements.getBlock=(pos,dx,dy,dz)=>{
    const b=getBlock(pos,dx,dy,dz)
    // An explicitly opened wooden door has a clear central corridor; never treat a
    // closed door as air or turn on pathfinder's unqualified automatic door toggles.
    if(clearDoor(b)) {
      b.safe=true;b.physical=false;b.openable=false;b.height=pos.y+dy
    }
    return b
  }
  if(bot)bot.on('path_update',result=>doorWaypoints(bot,result))
}
module.exports.configureMovements=configureMovements
module.exports.doorWaypoints=doorWaypoints

// Region selection is admitted by the application only after reviewing a durable manifest.
function region(value) {
  if(!value||!value.bounds||!Array.isArray(value.protected))throw Error('invalid_build_region')
  const {min,max}=value.bounds
  if(!min||!max||!['x','y','z'].every(k=>Number.isInteger(min[k])&&Number.isInteger(max[k])&&min[k]<=max[k]))throw Error('invalid_build_region')
  if(Math.abs(min.x)>29999000||Math.abs(max.x)>29999000||Math.abs(min.z)>29999000||Math.abs(max.z)>29999000||max.x-min.x>=256||max.z-min.z>=256||min.y< -60||max.y>63||value.protected.length>32)throw Error('build_region_bound')
  for(const box of value.protected)if(!box?.min||!box?.max||!['x','y','z'].every(k=>Number.isInteger(box.min[k])&&Number.isInteger(box.max[k])&&box.min[k]<=box.max[k]))throw Error('invalid_build_protection')
  if(value.observation_bounds){
    const b=value.observation_bounds
    if(!b.min||!b.max||!['x','y','z'].every(k=>b.min[k]===min[k]-(k==='y'?0:32)&&b.max[k]===max[k]+(k==='y'?0:32)))throw Error('invalid_observation_buffer')
  }
  return value
}
async function focus(bot,args,signal,bounds,emit) {
  if(bot.game.gameMode!=='creative')throw Error('creative_build_mode_required')
  const p=args.position
  if(!p||!Number.isInteger(p.x)||!Number.isInteger(p.z)||p.x<bounds.bounds.min.x||p.x>bounds.bounds.max.x||p.z<bounds.bounds.min.z||p.z>bounds.bounds.max.z)throw Error('focus_out_of_region')
  if(p.y!==bounds.bounds.max.y+8)throw Error('invalid_focus_height')
  signal.throwIfAborted()
  bot.creative.startFlying()
  const nonce=require('node:crypto').randomUUID().replaceAll('-','')
  let receipt=false
  const message=m=>{if(m.toString().includes('GC_BUILD_'+nonce))receipt=true}
  bot.on('message',message)
  try {
    emit('build_command',null,{operation:{mode:'focus',nonce,position:p}})
    const end=Date.now()+8000
    while(Date.now()<end){
      signal.throwIfAborted()
      const loaded=[[-40,-40],[40,-40],[-40,40],[40,40]].every(([x,z])=>bot.blockAt(new Vec3(p.x+x,bounds.bounds.min.y,p.z+z)))
      if(receipt&&loaded&&bot.entity.position.distanceTo(new Vec3(p.x,p.y,p.z))<3)return {observed:'terrain_chunks_ready',position:p}
      await new Promise(r=>setTimeout(r,30))
    }
    throw Error('terrain_chunks_unavailable')
  } finally {bot.removeListener('message',message)}
}
module.exports.region=region
module.exports.focus=focus
