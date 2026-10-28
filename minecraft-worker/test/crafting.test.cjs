const {test}=require('node:test');const assert=require('node:assert/strict')
const registry=require('minecraft-data')('1.21.4');const Recipe=require('prismarine-recipe')(registry).Recipe
const {resolve,craft}=require('../crafting.cjs')
function bot(items=[]) {return {registry,inventory:{items:()=>items,emptySlotCount:()=>30},recipesAll:id=>Recipe.find(id,null)}}
test('real recipes resolve variant yields, existing stock, table and tools',()=>{
 const b=bot([{name:'birch_log',count:2},{name:'birch_planks',count:1}]);const r=resolve(b,'birch_planks',10,'birch')
 assert.deepEqual(r.missing,{birch_log:1});assert.equal(r.steps[0].times,3);assert.equal(r.steps[0].yield,4)
 const t=resolve(bot(),'wooden_pickaxe',1,'oak');assert.equal(t.steps.filter(s=>s.workstation).length,1);assert.equal(t.missing.oak_log,3);assert(t.steps.at(-1).table)
 assert(resolve(bot(),'stone_pickaxe',1,'oak').missing.cobblestone===3)
})
test('dependency cycles and quantity/gather budgets fail closed',()=>{
 const b=bot();b.recipesAll=id=>[{result:{count:1},requiresTable:false,delta:[{id,count:-1}]}]
 assert.throws(()=>resolve(b,'oak_planks',2),/cyclic/)
 assert.throws(()=>resolve(bot(),'oak_planks',257),/invalid/)
 assert.throws(()=>resolve(bot(),'wooden_axe',100),/budget/)
})
test('craft rejects missing ingredients, capacity, workstation and unverified output',async()=>{
 const signal=new AbortController().signal
 await assert.rejects(craft(bot(),{item:'oak_planks',recipe:0,times:1},signal),/shortfall/)
 const b=bot([{name:'oak_log',count:1,stackSize:64}]);b.inventory.emptySlotCount=()=>0
 await assert.rejects(craft(b,{item:'oak_planks',recipe:0,times:1},signal),/inventory_full/)
 await assert.rejects(craft(bot(),{item:'wooden_pickaxe',recipe:0,times:1},signal),/workstation/)
 b.inventory.emptySlotCount=()=>30;b.craft=async()=>{}
 await assert.rejects(craft(b,{item:'oak_planks',recipe:0,times:1},signal),/not_verified/)
})
test('available workstation removes table creation from the dependency plan',()=>{
 const r=resolve(bot(),'wooden_pickaxe',1,'oak',true)
 assert(!r.steps.some(s=>s.workstation||s.item==='crafting_table'))
 assert.equal(r.missing.oak_log,2)
})
test('craft synchronizes every internal ingredient and output transfer across repeated executions',async()=>{
 const Item=require('prismarine-item')(registry)
 const windows=require('prismarine-windows')(registry)
 const w=windows.createWindow(0,'minecraft:inventory','Inventory')
 const log=registry.itemsByName.oak_log,plank=registry.itemsByName.oak_planks
 w.updateSlot(9,new Item(log.id,18))
 let synced=true, clicks=0
 const b={registry,inventory:w,recipesAll:id=>Recipe.find(id,null),
 _syncWindow:async()=>{synced=true},clickWindow:async(slot,button,mode)=>{
   assert(synced,'Every click must follow authoritative sync');synced=false;clicks++
   const result=slot===0
   w.acceptClick({slot,mouseButton:button,mode,item:w.slots[slot]})
   if(result){for(let n=1;n<=4;n++)if(w.slots[n]){w.updateSlot(n,null);break}}
   const ingredient=w.slots.slice(1,5).find(i=>i?.type===log.id)
   w.updateSlot(0,ingredient?new Item(plank.id,4):null)
 }}
 const r=await craft(b,{item:'oak_planks',recipe:0,times:9},new AbortController().signal)
 assert.equal(r.after.oak_log,9);assert.equal(r.after.oak_planks,36)
 assert.equal(w.selectedItem,null);assert(clicks>=36)
})
