'use strict'
const test=require('node:test'),assert=require('node:assert/strict')
const build=require('../build-service.cjs')
const registry=require('minecraft-data')('1.21.4')
const region={bounds:{min:{x:0,y:0,z:0},max:{x:63,y:63,z:63}},protected:[{min:{x:8,y:0,z:8},max:{x:15,y:63,z:15}}]}
test('canonical block states enforce game registry and bounded palette',()=>{
  assert.equal(build.allowed('stone',registry),registry.blocksByName.stone.defaultState)
  assert.throws(()=>build.allowed('stone;stop',registry))
  assert.throws(()=>build.allowed('command_block',registry))
  assert.throws(()=>build.allowed('oak_stairs[facing=invented]',registry))
})
test('regions protect boundaries and player-authored exclusion',()=>{
  build.check({x:1,y:1,z:1},region)
  assert.throws(()=>build.check({x:8,y:1,z:8},region))
  assert.throws(()=>build.check({x:64,y:1,z:1},region))
  assert.throws(()=>build.check({x:1.5,y:1,z:1},region))
})
test('only an opened door with a clear central corridor is traversable',()=>{
  let open=false
  const movements={getBlock:()=>({name:'oak_door',getProperties:()=>({open}),shapes:[[0,0,0,.1875,1,1]],safe:false,physical:true})}
  build.configureMovements(movements)
  assert.equal(movements.getBlock({y:2},0,0,0).safe,false)
  open=true
  const block=movements.getBlock({y:2},0,0,0)
  assert.equal(block.safe,true)
  assert.equal(block.physical,false)
  assert.equal(block.height,2)
})
test('door traversal targets the clear floor rather than the top of the leaf',()=>{
  const result={path:[{x:27.09375,y:-50,z:22.5}]}
  const bot={blockAt:()=>({name:'oak_door',position:{x:27,y:-50,z:22},getProperties:()=>({open:true,half:'upper'}),shapes:[[0,0,0,.1875,1,1]]})}
  build.doorWaypoints(bot,result)
  assert.deepEqual(result.path,[{x:27.5,y:-51,z:22.5}])
})

test('cached canonical states remain registry scoped and reject unknown properties',()=>{
  const registry=require('minecraft-data')('1.21.4')
  const stone=build.allowed('stone',registry)
  for(let i=0;i<100;i++)assert.equal(build.allowed('stone',registry),stone)
  assert.throws(()=>build.allowed('stone[unknown=true]',registry),/unknown_build_properties/)
  const other=require('minecraft-data')('1.20.4')
  assert.equal(build.allowed('stone',other),other.blocksByName.stone.defaultState)
})

test('expanded observation buffer is fixed and never expands write authority',()=>{
  const expanded={...region,observation_bounds:{min:{x:-32,y:0,z:-32},max:{x:95,y:63,z:95}}}
  assert.equal(build.region(expanded),expanded)
  assert.throws(()=>build.check({x:-1,y:1,z:0},expanded),/build_region_or_protection/)
  assert.throws(()=>build.region({...expanded,observation_bounds:{...expanded.observation_bounds,max:{x:96,y:63,z:95}}}),/invalid_observation_buffer/)
  assert.throws(()=>build.region({...region,protected:[{min:{x:1,y:0,z:0},max:{x:0,y:1,z:1}}]}),/invalid_build_protection/)
  assert.throws(()=>build.region({...region,bounds:{min:region.bounds.min,max:{x:256,y:63,z:63}}}),/build_region_bound/)
})

test('native beds and lights use exact registry states, never partial properties',()=>{
  for(const facing of ['north','east','south','west'])for(const part of ['head','foot']){
    const value=`white_bed[facing=${facing},occupied=false,part=${part}]`
    assert.equal(typeof build.allowed(value,registry),'number')
  }
  assert.equal(build.allowed('glowstone',registry),registry.blocksByName.glowstone.defaultState)
  assert.throws(()=>build.allowed('white_bed[facing=north]',registry),/unknown_build_properties/)
})
