// Read-only engineering observer. No operator commands, movement or inventory supply.
// A protocol character is not a human-client walkthrough.
const {createRequire}=require('module'), fs=require('fs'),path=require('path')
const req=createRequire(path.resolve(__dirname,'../minecraft-worker/package.json'))
const mineflayer=req('mineflayer'),{Vec3}=req('vec3')
const out=path.resolve(__dirname,'../artifacts/mc-b1-04-live-20261028')
const baseline=JSON.parse(fs.readFileSync(path.join(out,'protection-proof.json'))).before
const bot=mineflayer.createBot({host:'127.0.0.1',port:25575,username:'EvidenceObserver',auth:'offline',version:'1.21.4',hideErrors:true})
const timer=setTimeout(()=>{console.error('observer_timeout');bot.quit();process.exitCode=1},25000)
bot.once('spawn',async()=>{
 await bot.waitForChunksToLoad()
 const blocks=baseline.map(c=>{const b=bot.blockAt(new Vec3(c.position.x,c.position.y,c.position.z));return {position:c.position,expected:c.name,actual:b?.name||null,state_id:b?.stateId??null}})
 const result={at_ms:Date.now(),method:'read-only protocol observer; no operator privileges or world commands',observer_position:bot.entity.position,blocks,all_unchanged:blocks.every(b=>b.expected===b.actual)}
 fs.writeFileSync(path.join(out,'protection-authoritative-observer.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));clearTimeout(timer);bot.quit()
})
bot.on('error',e=>{console.error(e.message);clearTimeout(timer);process.exitCode=1})
