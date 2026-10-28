'use strict'
const { Vec3 } = require('vec3')
const LOGS = ['oak', 'birch', 'spruce', 'jungle', 'acacia', 'dark_oak', 'mangrove', 'cherry', 'pale_oak'].map(n => n + '_log')
const inside = (p, regions = []) => regions.some(r => Math.hypot(p.x - r.center.x, p.z - r.center.z) <= r.radius)
function regionsOf (regions = []) {
  if (!Array.isArray(regions) || regions.length > 16 || regions.some(r => !r.center || !['x', 'y', 'z'].every(k => Number.isFinite(r.center[k])) || !Number.isFinite(r.radius) || r.radius < 1 || r.radius > 32)) throw Error('invalid_protection')
  return regions
}
function resources (bot) {
  return bot.findBlocks({ matching: b => LOGS.includes(b.name), maxDistance: 32, count: 64 }).map(p => ({ name: bot.blockAt(p).name, position: p }))
}
function safeTarget (bot, p, regions) {
  if (inside(p, regions)) throw Error('protected_target')
  for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) {
    const b = bot.blockAt(new Vec3(Math.floor(p.x + x), Math.floor(p.y - 1), Math.floor(p.z + z)))
    if (b && ['lava', 'fire', 'cactus', 'magma_block', 'campfire'].includes(b.name)) throw Error('hazard_near_target')
  }
}
function chooseTool (bot, block) {
  if (!LOGS.includes(block.name)) throw Error('unsupported_resource')
  const options = bot.inventory.items().filter(i => i.name.endsWith('_axe'))
  options.sort((a, b) => block.digTime(a.type, false, false, false) - block.digTime(b.type, false, false, false))
  return options[0] || null
}
module.exports = { LOGS, inside, regionsOf, resources, safeTarget, chooseTool }
function visibleFrom (bot, feet, target) {
  const eye = feet.offset(0, 1.62, 0), center = target.offset(.5,.5,.5)
  const distance = eye.distanceTo(center)
  if (distance > 4.5) return false
  const hit = bot.world.raycast(eye, center.minus(eye).normalize(), distance + .1)
  return !!hit && hit.position.equals(target)
}
function stands (bot, target, regions) {
  const result = []
  for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let dy = -3; dy <= 0; dy++) {
    const p = target.offset(dx,dy,dz), feet = p.offset(.5,0,.5)
    const lower = bot.blockAt(p.offset(0,-1,0)), body = bot.blockAt(p), head = bot.blockAt(p.offset(0,1,0))
    if (!lower || !body || !head || lower.boundingBox !== 'block' || body.boundingBox !== 'empty' || head.boundingBox !== 'empty' || body.liquid || head.liquid || inside(feet, regions)) continue
    try { safeTarget(bot, feet, regions) } catch { continue }
    if (visibleFrom(bot, feet, target)) result.push(feet)
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
