'use strict'
const { LOGS } = require('./resource-skills.cjs')
const SUPPORTED = [...LOGS.map(n => n.replace('_log', '_planks')), 'stick', 'crafting_table', ...['wooden', 'stone'].flatMap(m => ['pickaxe','axe','shovel'].map(t => `${m}_${t}`))]
const counts = bot => { const items=(bot.currentWindow || bot.inventory).items(); return Object.fromEntries([...new Set(items.map(i=>i.name))].map(n=>[n,items.filter(i=>i.name===n).reduce((s,i)=>s+i.count,0)])) }
function recipes (bot, name) {
  if (!SUPPORTED.includes(name)) throw Error('unsupported_recipe')
  const item = bot.registry.itemsByName[name]
  return bot.recipesAll(item.id, null, true).map((r,index)=>({ index, item:name, yield:r.result.count, table:r.requiresTable, ingredients:r.delta.filter(d=>d.count<0).map(d=>({item:bot.registry.items[d.id].name,count:-d.count})), recipe:r }))
}
function resolve (bot, name, quantity, wood='oak', tableAvailable=false) {
  if (!Number.isInteger(quantity) || quantity<1 || quantity>256 || !LOGS.includes(wood+'_log')) throw Error('invalid_recipe_request')
  const stock=counts(bot), missing={}, steps=[]
  let operations=0, table=tableAvailable
  function need(n,q,trail=[]) {
    if (trail.includes(n) || trail.length>12) throw Error('cyclic_recipe_dependency')
    const have=Math.min(stock[n]||0,q); stock[n]=(stock[n]||0)-have; q-=have
    if (!q) return
    if (LOGS.includes(n) || n==='cobblestone') { missing[n]=(missing[n]||0)+q; return }
    const options=recipes(bot,n).filter(r=>r.ingredients.every(i=>(SUPPORTED.includes(i.item)||LOGS.includes(i.item)||i.item==='cobblestone') && (!i.item.endsWith('_planks') || i.item===wood+'_planks')))
    options.sort((a,b)=>b.ingredients.reduce((s,i)=>s+Math.min(stock[i.item]||0,i.count),0)-a.ingredients.reduce((s,i)=>s+Math.min(stock[i.item]||0,i.count),0))
    const r=options[0]; if(!r) throw Error('missing_or_unsupported_dependency:'+n)
    if(r.table&&!table) { need('crafting_table',1,[...trail,n]); table=true; steps.push({workstation:true}) }
    const times=Math.ceil(q/r.yield)
    operations+=times; if(operations>128) throw Error('craft_budget_exceeded')
    for(const i of r.ingredients) need(i.item,i.count*times,[...trail,n])
    steps.push({item:n,index:r.index,times,yield:r.yield,table:r.table,ingredients:r.ingredients})
    stock[n]=(stock[n]||0)+times*r.yield-q
  }
  need(name,quantity)
  if(Object.values(missing).reduce((s,n)=>s+n,0)>64) throw Error('gather_budget_exceeded')
  return {item:name,quantity,missing,steps,operations}
}
async function craft(bot,args,signal,table) {
  if(!Number.isInteger(args.times)||args.times<1||args.times>64) throw Error('invalid_craft_count')
  const r=recipes(bot,args.item).find(r=>r.index===args.recipe)
  if(!r) throw Error('invalid_recipe')
  if(r.table && (!table || table.name!=='crafting_table' || table.position.distanceTo(bot.entity.position)>4.5)) throw Error('workstation_unavailable_or_unreachable')
  if(bot._syncWindow) await bot._syncWindow(bot.inventory)
  signal.throwIfAborted()
  let before=counts(bot)
  for(const i of r.ingredients) if((before[i.item]||0)<i.count*args.times) throw Error('ingredient_shortfall:'+i.item)
  // Conservative capacity check includes output without assuming ingredients free a slot.
  const item=bot.registry.itemsByName[args.item]
  const capacity=bot.inventory.emptySlotCount()*item.stackSize+bot.inventory.items().filter(i=>i.name===args.item).reduce((s,i)=>s+i.stackSize-i.count,0)
  if(capacity<r.yield*args.times) throw Error('inventory_full')
  // Every click, including putting away ingredients/output, crosses a full
  // server-window synchronization. Mineflayer's craft helper calls private
  // click closures for putAway, which cannot be synchronized by wrapping its
  // public clickWindow alone.
  if (!bot._syncWindow || !bot.clickWindow) throw Error('craft_inventory_change_not_verified')
  let window = bot.inventory
  if (r.table) {
    const { once } = require('node:events')
    const opened = once(bot, 'windowOpen', { signal })
    await bot.activateBlock(table)
    ;[window] = await opened
  }
  const click = async (slot, button=0) => {
    signal.throwIfAborted()
    await bot.clickWindow(slot, button, 0)
    await bot._syncWindow(window)
    signal.throwIfAborted()
  }
  const stash = async () => {
    for (let n=0; window.selectedItem && n<46; n++) {
      const held=window.selectedItem
      const partial=window.findItemRange(window.inventoryStart,window.inventoryEnd,held.type,held.metadata,true,held.nbt)
      const slot=partial?.slot ?? window.firstEmptySlotRange(window.inventoryStart,window.inventoryEnd)
      if(slot===null) throw Error('inventory_full_cursor_retained')
      const count=held.count
      await click(slot)
      if(window.selectedItem?.type===held.type && window.selectedItem.count>=count) throw Error('cursor_transfer_unverified')
    }
    if(window.selectedItem) throw Error('cursor_recovery_budget')
  }
  try {
    await bot._syncWindow(window)
    await stash()
    const width=r.table?3:2
    for(let slot=1;slot<=width*width;slot++) {
      if(window.slots[slot]) { await click(slot); await stash() }
    }
    // Reconcile any ingredients retained in the cursor/grid by an interrupted
    // previous craft. They are observed inventory, never manufactured refunds.
    const baseline=counts(bot)
    before=baseline
    const cells=[]
    if(r.recipe.inShape) {
      r.recipe.inShape.forEach((row,y)=>row.forEach((v,x)=>{if(v.id!==-1)cells.push({slot:1+x+y*width,id:v.id,metadata:v.metadata})}))
    } else {
      r.recipe.ingredients.forEach((v,i)=>{if(v.id!==-1)cells.push({slot:1+i,id:v.id,metadata:v.metadata})})
    }
    for(let i=0;i<args.times;i++) {
      signal.throwIfAborted()
      for(const cell of cells) {
        const source=window.findInventoryItem(cell.id,cell.metadata)
        if(!source) throw Error('ingredient_shortfall_after_reconciliation')
        await click(source.slot)
        await click(cell.slot,1)
        await stash()
      }
      const output=window.slots[0]
      if(!output || output.type!==item.id || output.count!==r.yield) throw Error('server_craft_output_unverified')
      await click(0)
      await stash()
      const actual=counts(bot)
      if((actual[args.item]||0)-(baseline[args.item]||0)!==r.yield*(i+1) || r.ingredients.some(d=>(baseline[d.item]||0)-(actual[d.item]||0)!==d.count*(i+1))) throw Error('craft_inventory_change_not_verified:'+JSON.stringify({execution:i+1,before:baseline,after:actual}))
    }
  } finally {
    if(r.table && bot.currentWindow===window) {
      await bot.closeWindow(window)
      await bot._syncWindow(bot.inventory)
    }
  }
  // craft() synchronizes the server window; wait for the resulting inventory observation.
  await new Promise(r=>setTimeout(r,150)); signal.throwIfAborted()
  const after=counts(bot)
  if((after[args.item]||0)-(before[args.item]||0)!==r.yield*args.times || r.ingredients.some(i=>(before[i.item]||0)-(after[i.item]||0)!==i.count*args.times)) throw Error('craft_inventory_change_not_verified')
  return {observed:'inventory_delta',before,after,item:args.item,executions:args.times,yield:r.yield,workstation:table?.position||null}
}
module.exports={SUPPORTED,counts,recipes,resolve,craft}
