const { test } = require('node:test')
const assert = require('node:assert/strict')
const { inside, regionsOf, chooseTool, safeTarget } = require('../resource-skills.cjs')
test('protections validate boundaries and reject targets', () => {
  const regions = regionsOf([{ center: { x: 0, y: 0, z: 0 }, radius: 3 }])
  assert.equal(inside({ x: 3, z: 0 }, regions), true)
  assert.throws(() => regionsOf([{ center: {}, radius: 3 }]), /invalid_protection/)
  assert.throws(() => safeTarget({}, { x: 2, z: 0 }, regions), /protected_target/)
})
test('available faster axe wins; hand is valid for logs; other resources refused', () => {
  const block = { name: 'oak_log', digTime: type => type === 2 ? 100 : 900 }
  const bot = { inventory: { items: () => [{ name: 'wooden_axe', type: 1 }, { name: 'iron_axe', type: 2 }, { name: 'diamond_sword', type: 3 }] } }
  assert.equal(chooseTool(bot, block).name, 'iron_axe')
  bot.inventory.items = () => []
  assert.equal(chooseTool(bot, block), null)
  assert.throws(() => chooseTool(bot, { name: 'stone' }), /missing_harvest_tool/)
})
test('nearby lava fails before movement', () => {
  assert.throws(() => safeTarget({ blockAt: () => ({ name: 'lava' }) }, { x: 0, y: 0, z: 0 }, []), /hazard/)
})
test('batched authoritative changes decode exact positions including negative sections', () => {
  const { multiChanges } = require('../resource-skills.cjs')
  const record = (1234 << 12) | (3 << 8) | (7 << 4) | 5
  assert.deepEqual(multiChanges({chunkCoordinates:{x:-1,y:-4,z:2},records:[record]}), [{location:{x:-13,y:-59,z:39},type:1234}])
})
test('block visibility requires a clear ray and survival reach', () => {
  const { visibleFrom } = require('../resource-skills.cjs')
  const { Vec3 } = require('vec3')
  const p = new Vec3(0,0,0), target = new Vec3(1,0,0)
  assert.equal(visibleFrom({world:{raycast:()=>({position:target})}}, p, target), true)
  assert.equal(visibleFrom({world:{raycast:()=>({position:new Vec3(0,0,0)})}}, p, target), false)
  assert.equal(visibleFrom({}, p, new Vec3(10,0,0)), false)
})
test('active goal guard catches distance, world changes and survival danger', () => {
  const { goalGuard } = require('../resource-skills.cjs'), { Vec3 } = require('vec3')
  const bot = {entity:{position:new Vec3(0,64,0)},game:{dimension:'overworld'},health:20,food:20}
  const args = {world:['one','overworld','1.21.4'],goal_origin:{x:0,y:64,z:0}}
  assert.equal(goalGuard(bot,args,'one'),null)
  bot.entity.position.x = 33
  assert.equal(goalGuard(bot,args,'one'),'goal_distance_limit')
  bot.entity.position.x = 0; bot.game.dimension = 'the_nether'
  assert.equal(goalGuard(bot,args,'one'),'stale_world')
  bot.game.dimension = 'overworld'; bot.health = 4
  assert.equal(goalGuard(bot,args,'one'),'survival_health_or_food_limit')
})
test('stone harvestability is distinct from breaking speed',()=>{
 const block={name:'stone',canHarvest:type=>type===2,digTime:type=>type===1?1:1000}
 const bot={inventory:{items:()=>[{name:'wooden_axe',type:1},{name:'wooden_pickaxe',type:2}]}}
 assert.equal(chooseTool(bot,block).name,'wooden_pickaxe')
 bot.inventory.items=()=>[{name:'wooden_axe',type:1}]
 assert.throws(()=>chooseTool(bot,block),/missing_harvest_tool/)
})
test('low food and death are unsafe even without a parent goal', () => {
  const { goalGuard } = require('../resource-skills.cjs'), { Vec3 } = require('vec3')
  const bot={entity:{position:new Vec3(0,64,0)},game:{dimension:'overworld'},health:20,food:4}
  assert.equal(goalGuard(bot,{},'one'),'survival_health_or_food_limit')
  bot.food=20; bot.health=0
  assert.equal(goalGuard(bot,{},'one'),'survival_health_or_food_limit')
})

test('relative travel chooses observed terrain without changing saved coordinates',()=>{
 const {surfaceDestinations}=require('../resource-skills.cjs'), {Vec3}=require('vec3')
 const b={entity:{position:new Vec3(0,1,0)},blockAt:p=>p.y===2?{name:'grass_block',boundingBox:'block'}:{name:'air',boundingBox:'empty'}}
 const sites=surfaceDestinations(b,new Vec3(10,1,0),[])
 assert(sites.length>0);assert(sites.every(p=>p.y===3))
 assert.equal(surfaceDestinations(b,new Vec3(10,1,0),[{center:new Vec3(10,1,0),radius:3}]).length,0)
})
test('connected branches share stable failure identity; changed terrain changes fingerprint',()=>{
 const {resources}=require('../resource-skills.cjs'),{Vec3}=require('vec3')
 let points=[new Vec3(0,1,0),new Vec3(0,2,0),new Vec3(1,2,0)],changed=false
 const b={entity:{position:new Vec3(0,20,0)},findBlocks:args=>args.maxDistance===32?points:[],blockAt:p=>({name:points.some(q=>q.equals(p))?'oak_log':'air',stateId:changed&&p.x===2?9:1})}
 const first=resources(b);assert.equal(new Set(first.map(x=>x.cluster)).size,1)
 points=points.reverse();assert.equal(resources(b)[0].signature,first[0].signature)
 changed=true;assert.notEqual(resources(b)[0].signature,first[0].signature)
})
