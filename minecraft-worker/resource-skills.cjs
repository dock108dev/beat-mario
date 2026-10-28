'use strict'
const { Vec3 } = require('vec3')
const LOGS = ['oak', 'birch', 'spruce', 'jungle', 'acacia', 'dark_oak', 'mangrove', 'cherry', 'pale_oak'].map(n => n + '_log')
const inside = (p, regions = []) => regions.some(r => Math.hypot(p.x - r.center.x, p.z - r.center.z) <= r.radius)
function regionsOf (regions = []) {
  if (!Array.isArray(regions) || regions.length > 16 || regions.some(r => !r.center || !['x', 'y', 'z'].every(k => Number.isFinite(r.center[k])) || !Number.isFinite(r.radius) || r.radius < 1 || r.radius > 32)) throw Error('invalid_protection')
  return regions
}
function resources (bot) {
  const points = [...bot.findBlocks({ matching: b => LOGS.includes(b.name), maxDistance: 32, count: 256 }), ...bot.findBlocks({matching:b=>['stone','cobblestone'].includes(b.name),maxDistance:16,count:16})]
  const columns = new Map()
  for (const p of points) {
    const key = `${p.x},${p.z}`
    if (!columns.has(key) || columns.get(key).y > p.y) columns.set(key, p)
  }
  const connected = new Map(points.map(p=>[`${p.x},${p.y},${p.z}`,p]))
  const clusters = new Map()
  for(const start of points) {
    if(clusters.has(`${start.x},${start.z}`))continue
    const queue=[start], seen=new Set(), cols=[]
    while(queue.length) {
      const p=queue.pop(), id=`${p.x},${p.y},${p.z}`
      if(seen.has(id))continue
      seen.add(id);cols.push(`${p.x},${p.z}`)
      for(let x=-1;x<=1;x++)for(let y=-1;y<=1;y++)for(let z=-1;z<=1;z++) {
        const q=connected.get(`${p.x+x},${p.y+y},${p.z+z}`)
        if(q&&!seen.has(`${q.x},${q.y},${q.z}`))queue.push(q)
      }
    }
    const cluster=[...new Set(cols)].sort().join(';')
    for(const col of cols)clusters.set(col,cluster)
  }
  const metadata = new Map()
  for (const [key, p] of columns) {
    // Stable across vertical blocks; changed nearby terrain permits immediate retry.
    const states=[]
    for(let x=-2;x<=2;x++)for(let z=-2;z<=2;z++)for(let y=-3;y<=3;y++)states.push(bot.blockAt(p.offset(x,y,z))?.stateId ?? -1)
    const signature=require('node:crypto').createHash('sha256').update(states.join(',')).digest('hex').slice(0,16)
    metadata.set(key,{cluster:clusters.get(key)||key,signature})
  }
  const shared = new Map()
  for(const [,m] of [...metadata.entries()].sort((a,b)=>a[0].localeCompare(b[0])))shared.set(m.cluster,(shared.get(m.cluster)||'')+m.signature)
  for(const m of metadata.values())m.signature=require('node:crypto').createHash('sha256').update(shared.get(m.cluster)).digest('hex').slice(0,16)
  return points.map(p => ({ name: bot.blockAt(p).name, position: p, ...metadata.get(`${p.x},${p.z}`), accessible: p.y>=bot.entity.position.y-1 && p.y<=bot.entity.position.y+4 && stands(bot,p,[]).length>0 }))
}
function scoutSites(bot) {
  const base=bot.entity.position.floored(), result=[]
  for(const [x,z] of [[12,0],[-12,0],[0,12],[0,-12],[9,9],[-9,9],[9,-9],[-9,-9]])for(const y of [0,1,-1,2,-2]) {
    const p=base.offset(x,y,z), ground=bot.blockAt(p.offset(0,-1,0)), body=bot.blockAt(p), head=bot.blockAt(p.offset(0,1,0))
    if(ground?.boundingBox==='block' && body?.name==='air' && head?.name==='air') {
      try {safeTarget(bot,p,[]);result.push(p);break}catch{}
    }
  }
  return result
}
function safeTarget (bot, p, regions) {
  if (inside(p, regions)) throw Error('protected_target')
  for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) {
    const b = bot.blockAt(new Vec3(Math.floor(p.x + x), Math.floor(p.y - 1), Math.floor(p.z + z)))
    if (b && ['lava', 'fire', 'cactus', 'magma_block', 'campfire'].includes(b.name)) throw Error('hazard_near_target')
  }
}
function chooseTool (bot, block) {
  if (!MINEABLE.includes(block.name)) throw Error('unsupported_resource')
  if (!LOGS.includes(block.name)) {
    const tools=bot.inventory.items().filter(i=>block.canHarvest(i.type))
    tools.sort((a,b)=>block.digTime(a.type,false,false,false)-block.digTime(b.type,false,false,false))
    if(!tools.length) throw Error('missing_harvest_tool')
    return tools[0]
  }
  const options = bot.inventory.items().filter(i => i.name.endsWith('_axe'))
  options.sort((a, b) => block.digTime(a.type, false, false, false) - block.digTime(b.type, false, false, false))
  return options[0] || null
}
const MINEABLE = [...LOGS, 'stone', 'cobblestone']
module.exports = { MINEABLE, LOGS, scoutSites, inside, regionsOf, resources, safeTarget, chooseTool }
function visibleFrom (bot, feet, target) {
  const eye = feet.offset(0, 1.62, 0), center = target.offset(.5,.5,.5)
  const distance = eye.distanceTo(center)
  if (distance > 4.5) return false
  const hit = bot.world.raycast(eye, center.minus(eye).normalize(), distance + .1)
  return !!hit && hit.position.equals(target)
}
function stands (bot, target, regions, maxDy = 0) {
  const result = []
  for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let dy = -4; dy <= maxDy; dy++) {
    const p = target.offset(dx,dy,dz), feet = p.offset(.5,0,.5)
    const lower = bot.blockAt(p.offset(0,-1,0)), body = bot.blockAt(p), head = bot.blockAt(p.offset(0,1,0))
    if (!lower || !body || !head || lower.boundingBox !== 'block' || body.boundingBox !== 'empty' || head.boundingBox !== 'empty' || body.liquid || head.liquid || inside(feet, regions)) continue
    try { safeTarget(bot, feet, regions) } catch { continue }
    if (feet.distanceTo(target)<=4.5 && visibleFrom(bot, feet, target)) result.push(feet)
  }
  return result.sort((a,b)=>a.distanceTo(bot.entity.position)-b.distanceTo(bot.entity.position))
}
function multiChanges (packet) {
  return packet.records.map(record => ({
    location: { x: packet.chunkCoordinates.x * 16 + ((record >> 8) & 15), y: packet.chunkCoordinates.y * 16 + (record & 15), z: packet.chunkCoordinates.z * 16 + ((record >> 4) & 15) },
    type: record >> 12
  }))
}
Object.assign(module.exports, { visibleFrom, stands, multiChanges })

function goalGuard (bot, args, worldId) {
  if (!bot.entity || !bot.game) return 'game_state_unavailable'
  if (args.world && JSON.stringify(args.world) !== JSON.stringify([worldId, bot.game.dimension, '1.21.4'])) return 'stale_world'
  if (args.goal_origin) {
    if (!['x','y','z'].every(k=>Number.isFinite(args.goal_origin[k]))) return 'invalid_goal_origin'
    const origin = new Vec3(args.goal_origin.x,args.goal_origin.y,args.goal_origin.z)
    if (bot.entity.position.distanceTo(origin) > 32) return 'goal_distance_limit'
  }
  if (bot.health <= 6 || bot.food <= 4) return 'survival_health_or_food_limit'
  return null
}
module.exports.goalGuard = goalGuard

function surfaceDestinations(bot,target,regions) {
  const result=[]
  for(let dx=-1;dx<=1;dx++)for(let dz=-1;dz<=1;dz++)for(let dy=-4;dy<=4;dy++) {
    const p=target.floored().offset(dx,dy,dz),ground=bot.blockAt(p.offset(0,-1,0)),body=bot.blockAt(p),head=bot.blockAt(p.offset(0,1,0))
    if(p.distanceTo(bot.entity.position)>31 || inside(p,regions))continue
    if(ground?.boundingBox==='block' && body?.name==='air' && head?.name==='air') {
      try {safeTarget(bot,p,regions);result.push(p)}catch{}
    }
  }
  return result.sort((a,b)=>Math.hypot(a.x-target.x,a.z-target.z)-Math.hypot(b.x-target.x,b.z-target.z)||Math.abs(a.y-target.y)-Math.abs(b.y-target.y)).slice(0,12)
}
module.exports.surfaceDestinations=surfaceDestinations
