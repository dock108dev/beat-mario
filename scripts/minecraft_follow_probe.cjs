// Engineering-only protocol character; never a human-client walkthrough.
const { createRequire } = require('module')
const req = createRequire(require('path').resolve(__dirname, '../minecraft-worker/package.json'))
const mineflayer = req('mineflayer')
const { pathfinder, Movements, goals } = req('mineflayer-pathfinder')
const bot = mineflayer.createBot({host:'127.0.0.1',port:25575,username:'FollowProbe',version:'1.21.4',auth:'offline',hideErrors:true})
bot.loadPlugin(pathfinder)
let origin, running=true
const delay=ms=>new Promise(r=>setTimeout(r,ms))
bot.once('spawn', async()=>{
  await bot.waitForChunksToLoad()
  const m=new Movements(bot);m.canDig=false;m.allow1by1towers=false;m.scafoldingBlocks=[];m.allowParkour=false
  bot.pathfinder.setMovements(m)
  let target
  for(let i=0;i<100 && !target;i++){target=bot.players.CompanionBot?.entity;if(!target)await delay(100)}
  if(!target)throw Error('CompanionBot not observed by probe')
  origin=target.position.clone()
  await bot.pathfinder.goto(new goals.GoalNear(origin.x+5,origin.y,origin.z,1))
  console.log(JSON.stringify({kind:'ready',at_ms:Date.now(),origin}))
  while(running){for(const dx of [14,-10]){if(!running)break;try{await bot.pathfinder.goto(new goals.GoalNear(origin.x+dx,origin.y,origin.z,1))}catch{}await delay(600)}}
})
setInterval(()=>{if(bot.entity)console.log(JSON.stringify({kind:'position',at_ms:Date.now(),position:bot.entity.position,companion:bot.players.CompanionBot?.entity?.position}))},500).unref()
function close(){running=false;bot.pathfinder.setGoal(null);bot.clearControlStates();bot.quit();setTimeout(()=>process.exit(),500)}
process.on('SIGTERM',close);process.on('SIGINT',close);setTimeout(close,600000)
bot.on('error',e=>console.error(e.message))
bot.on('end',()=>process.exit(0))
