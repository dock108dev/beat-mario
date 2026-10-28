const {test}=require('node:test'),assert=require('node:assert/strict'),{Vec3}=require('vec3')
const {pathLength,reservation,route,select,oscillating}=require('../routes.cjs')
test('travel accounting uses path length, including bends, and reserves a conservative return',()=>{
 assert.equal(pathLength({x:0,y:0,z:0},[{x:3,y:0,z:0},{x:3,y:0,z:4}]),7)
 assert(reservation({known:true,length:10},{known:true,length:30},100).allowed)
 assert(!reservation({known:true,length:30},{known:true,length:40},100).allowed)
 assert(!reservation({known:true,length:0},{known:false},0).allowed)
})
test('unknown, destructive and outside-parent routes are never treated as feasible',()=>{
 const b={pathfinder:{movements:{},getPathFromTo:function*(){yield {result:{status:'partial',path:[]}}}}}
 assert(!route(b,new Vec3(0,0,0),new Vec3(2,0,0)).known)
 b.pathfinder.getPathFromTo=function*(){yield {result:{status:'success',path:[{x:40,y:0,z:0}]}}}
 assert(!route(b,new Vec3(0,0,0),new Vec3(2,0,0),{goal_origin:{x:0,y:0,z:0}}).known)
 b.pathfinder.getPathFromTo=function*(){yield {result:{status:'success',path:[{x:2,y:0,z:0,toBreak:[{}]}]}}}
 assert(!route(b,new Vec3(0,0,0),new Vec3(2,0,0)).known)
})
test('oscillating path is stopped but forward travel is not',()=>{
 const samples=[{at:0,travel:0,position:{x:0,y:0,z:0}},{at:3000,travel:8,position:{x:0,y:0,z:0}}]
 assert(oscillating(samples));samples[1].position.x=8;assert(!oscillating(samples))
})
test('candidate route reserve failure leaves return allowance unspent',()=>{
 const b={entity:{position:new Vec3(0,0,0)},pathfinder:{movements:{},getPathFromTo:function*(m,start,goal){yield {result:{status:'success',path:[{x:0,y:0,z:30},{x:goal.x,y:goal.y,z:goal.z}]}}}}}
 assert.throws(()=>select(b,[new Vec3(20,0,0)],{return_target:{x:0,y:0,z:0}},100),/reserve/)
})
test('blocked step is the next segment near the bot, not an already traversed node',()=>{
 const {blockedStep}=require('../routes.cjs')
 const path=[{x:-7.5,y:65,z:89.5},{x:-3.5,y:65,z:89.5},{x:-2.5,y:65,z:89.5},{x:-1.5,y:64,z:88.5}]
 assert(blockedStep(path,new Vec3(-2.3,65,89.23)).equals(new Vec3(-2,64,88)))
})
test('route goals and execution agree on fractional saved-place coordinates',()=>{
 let captured
 const b={pathfinder:{movements:{},getPathFromTo:function*(m,s,g){captured=g;yield {result:{status:'success',path:[]}}}}}
 route(b,new Vec3(0,0,0),{x:10.5,y:64,z:83.5})
 assert.equal(captured.x,10);assert.equal(captured.z,83)
})
