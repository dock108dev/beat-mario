// Engineering assistance only, on the separate loopback Survival test world.
// This protocol character is never counted as a human walkthrough.
const { createRequire } = require('module')
const req = createRequire(require('path').resolve(__dirname, '../minecraft-worker/package.json'))
const mineflayer = req('mineflayer')
const { Vec3 } = req('vec3')
const bot = mineflayer.createBot({host:'127.0.0.1', port:25575, username:'EngineeringProbe', version:'1.21.4', auth:'offline', hideErrors:true})
const delay = ms => new Promise(r => setTimeout(r, ms))
const emit = (kind, data = {}) => console.log(JSON.stringify({at_ms:Date.now(),kind,...data}))
let saved = [], interval
bot.once('spawn', async () => {
  await bot.waitForChunksToLoad()
  emit('ready', {position:bot.entity.position})
  interval = setInterval(() => emit('sample', {companion:bot.players.CompanionBot?.entity?.position, position:bot.entity.position}), 500)
})
async function command (line) {
  const p = bot.players.CompanionBot?.entity?.position
  emit('assistance', {command:line, companion:p})
  if (line === 'axes') { bot.chat('/give CompanionBot minecraft:wooden_axe 1'); await delay(500); bot.chat('/give CompanionBot minecraft:iron_axe 1') }
  else if (line === 'near') bot.chat('/tp EngineeringProbe CompanionBot')
  else if (line === 'far' && p) bot.chat(`/tp EngineeringProbe ${p.x + 33} ${p.y} ${p.z}`)
  else if (line === 'cage' && p) {
    const center = p.floored()
    for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) for (let y = 0; y <= 2; y++) {
      if (x === 0 && z === 0) continue
      const pos = center.plus(new Vec3(x,y,z)), block = bot.blockAt(pos)
      if (!block || block.name !== 'air') continue // never overwrite natural blocks
      saved.push(pos)
      bot.chat(`/setblock ${pos.x} ${pos.y} ${pos.z} minecraft:glass`)
      await delay(100)
    }
    emit('cage_ready', {positions:saved})
  } else if (line === 'uncage') {
    for (const pos of saved) { bot.chat(`/setblock ${pos.x} ${pos.y} ${pos.z} minecraft:air`); await delay(100) }
    saved = []
  } else if (line === 'trees') {
    const blocks = bot.findBlocks({matching:b=>b.name.endsWith('_log'), maxDistance:32, count:256}).map(pos=>({position:pos,name:bot.blockAt(pos).name}))
    emit('trees', {blocks})
  } else if (line === 'quit') { clearInterval(interval); bot.quit(); setTimeout(()=>process.exit(),500) }
}
require('readline').createInterface({input:process.stdin}).on('line', line=>command(line.trim()).catch(e=>emit('error',{message:e.message})))
bot.on('messagestr', text => emit('server_message',{text}))
bot.on('error',e=>emit('error',{message:e.message}))
bot.on('end',()=>process.exit())
setTimeout(()=>command('quit'),900000).unref()
