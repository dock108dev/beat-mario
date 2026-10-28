const {test}=require('node:test');const assert=require('node:assert/strict');const {EventEmitter}=require('node:events');const {Vec3}=require('vec3')
const {inspect,place}=require('../construction.cjs')
const p=new Vec3(2,1,0), support={name:'stone',position:new Vec3(2,0,0),boundingBox:'block'}
function bot(){const b={entity:{position:new Vec3(0,1,0)},entities:{},game:{gameMode:'survival'},_client:new EventEmitter(),world:{raycast:()=>support},inventory:{items:()=>[{name:'oak_planks',count:5,stackSize:64}]},blockAt:v=>v.y===0?support:{name:'air',stateId:0,position:v,boundingBox:'empty'},equip:async()=>{}};return b}
const args={target:{x:2,y:1,z:0},item:'oak_planks'}
test('preflight distinguishes occupancy support protection and unknown terrain',()=>{
 const b=bot(),cells=[{position:args.target,item:args.item}]
 assert.equal(inspect(b,{cells},[]).occupied.length,0)
 assert.equal(inspect(b,{cells},[{center:p,radius:1}]).protected.length,1)
 b.blockAt=()=>({name:'dirt',boundingBox:'block'});assert.equal(inspect(b,{cells},[]).occupied.length,1)
 b.blockAt=()=>null;assert.equal(inspect(b,{cells},[]).unknown.length,1)
})
test('placement rejects occupied cells, absent support and depleted inventory',async()=>{
 const signal=new AbortController().signal,b=bot()
 b.blockAt=()=>({name:'dirt',boundingBox:'block'});await assert.rejects(place(b,args,signal,[],{}),/occupied/)
 b.blockAt=v=>({name:'air',boundingBox:'empty'});await assert.rejects(place(b,args,signal,[],{}),/support/)
 const c=bot();c.inventory.items=()=>[];await assert.rejects(place(c,args,signal,[],{}),/shortfall/)
})
test('placement requires authoritative packet AND inventory consumption',async()=>{
 const b=bot(),signal=new AbortController().signal
 b.placeBlock=async()=>{b.blockAt=v=>v.equals(p)?{name:'oak_planks',stateId:15}:support;b._client.emit('block_change',{location:p,type:15});b.inventory.items=()=>[{name:'oak_planks',count:4}]}
 const result=await place(b,args,signal,[],{});assert.equal(result.observed,'server_placement');assert.equal(result.consumed,1)
 assert.equal(b._client.listenerCount('block_change'),0)
 const c=bot();c.placeBlock=async()=>{c.blockAt=v=>v.equals(p)?{name:'oak_planks',stateId:15}:support;c.inventory.items=()=>[{name:'oak_planks',count:4}]}
 await assert.rejects(place(c,args,signal,[],{}),/not_verified/)
})
test('a table immediately inside a planned doorway blocks revision preflight',()=>{
 const cells=[]
 for(let y=1;y<=3;y++)for(let x=0;x<4;x++)for(let z=0;z<4;z++)if(y===3||x===0||x===3||z===0||z===3)if(!(x===2&&z===0&&y<3))cells.push({position:{x,y,z},item:'oak_planks'})
 const b=bot();b.blockAt=v=>v.y===0?{name:'stone',boundingBox:'block'}:v.x===2&&v.y===1&&v.z===1?{name:'crafting_table',boundingBox:'block'}:{name:'air',boundingBox:'empty'}
 assert(inspect(b,{cells,clearance:true},[]).occupied.some(c=>c.actual==='crafting_table'))
})
test('adjacent structure cannot block the exterior doorway',()=>{
 const cells=[]
 for(let y=1;y<=3;y++)for(let x=0;x<4;x++)for(let z=0;z<4;z++)if(y===3||x===0||x===3||z===0||z===3)if(!(x===2&&z===3&&y<3))cells.push({position:{x,y,z},item:'oak_planks'})
 const b=bot();b.blockAt=v=>v.y===0?{name:'stone',boundingBox:'block'}:v.z===4&&v.y<3?{name:'oak_planks',boundingBox:'block'}:{name:'air',boundingBox:'empty'}
 assert(inspect(b,{cells,clearance:true},[]).occupied.some(c=>c.access&&c.position.z===4))
})
test('survey returns separated alternatives and rejection reasons without editing terrain',()=>{
 const {survey}=require('../construction.cjs'), b=bot()
 b.blockAt=v=>({name:'stone',boundingBox:'block',position:v})
 const result=survey(b,{cells:[{position:{x:2,y:1,z:0},item:'oak_planks'}]},[])
 assert.equal(result.observed,'site_search_exhausted')
 assert(result.inspected<=96)
 assert(result.rejected.some(r=>r.reasons.occupied>0))
 assert.equal(new Set(result.rejected.map(r=>JSON.stringify(r.origin))).size,result.inspected)
})
test('preflight detects absence of any placement standing area',()=>{
 const b=bot(), cells=[{position:{x:2,y:1,z:0},item:'oak_planks'}]
 b.blockAt=v=>v.y===0?{name:'air',boundingBox:'empty'}:{name:'air',boundingBox:'empty'}
 assert.equal(inspect(b,{cells,clearance:true},[]).inaccessible.length,1)
})
test('survey reuses unchanged rejection and reconsiders changed terrain',()=>{
 const {survey}=require('../construction.cjs'),b=bot();let changed=false
 b.blockAt=v=>({name:'stone',stateId:changed?2:1,boundingBox:'block',position:v})
 const args={cells:[{position:{x:2,y:1,z:0},item:'oak_planks'}]}
 const first=survey(b,args,[])
 const records=first.rejected.map(r=>({...r,at_ms:Date.now()}))
 const again=survey(b,{...args,rejections:records},[])
 assert.equal(again.inspected,0);assert.equal(again.reused,records.length)
 changed=true
 const fresh=survey(b,{...args,rejections:records},[])
 assert(fresh.inspected>0);assert.equal(fresh.reused,0)
})
test('a geometric site is not offered without complete observed routes',()=>{
 const {survey}=require('../construction.cjs'),b=bot()
 b.pathfinder={movements:{},getPathFromTo:function*(){yield {result:{status:'partial',path:[]}}}}
 const args={cells:[{position:{x:2,y:1,z:0},item:'oak_planks'}]}
 const no=survey(b,args,[]);assert.equal(no.observed,'site_search_exhausted');assert(no.rejected.some(r=>r.reasons.route_access))
 b.pathfinder.getPathFromTo=function*(m,start,goal){yield {result:{status:'success',path:[{x:goal.x,y:goal.y,z:goal.z}]}}}
 const yes=survey(b,args,[]);assert.equal(yes.observed,'site');assert(yes.access.known)
 const blocked=survey(b,args,[{center:new Vec3(0,1,0),radius:32}]);assert.equal(blocked.observed,'site_search_exhausted')
})
