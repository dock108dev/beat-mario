'use strict'
// Integrates Prismarine WorldView directly: upstream helper binds all interfaces.
const express = require('express')
const { createServer } = require('node:http')
const { Server } = require('socket.io')
const { WorldView } = require('prismarine-viewer/viewer/lib/worldView')
const { pixelClass, installPixelProbe, attachPixelMeasurements } = require('./viewer-pixel.cjs')
const { setupRoutes } = require('prismarine-viewer/lib/common')

async function openViewer (bot, session, port, report) {
  const app = express()
  const http = createServer(app)
  const allowed = value => !value || value === `http://127.0.0.1:${http.address()?.port}`
  app.use((req, res, next) => {
    if (req.headers.host !== `127.0.0.1:${http.address()?.port}` || !allowed(req.headers.origin)) return res.sendStatus(403)
    next()
  })
  app.get('/session', (req, res) => res.json({ session_id: session, character: bot.username, policy: 'Bot work continues when viewer closes. Stop is in the application.' }))
  // Prismarine 1.33.0's camera initialization incorrectly excludes negative Y.
  // Serve a narrowly checked compatibility patch without editing node_modules.
  const fs = require('node:fs')
  let bundle = fs.readFileSync(require.resolve('prismarine-viewer/public/index.js'), 'utf8')
  const needle = 't.y>0&&s&&(h.target.set(t.x,t.y,t.z),u.camera.position.set(t.x,t.y+20,t.z+20),h.update(),s=!1)'
  const cameraFollow = 'Number.isFinite(t.y)&&(s?(u.camera.position.set(t.x,t.y+12,t.z+12),s=!1):(u.camera.position.x+=t.x-h.target.x,u.camera.position.y+=t.y-h.target.y,u.camera.position.z+=t.z-h.target.z),h.target.set(t.x,t.y,t.z),h.update())'
  if (bundle.split(needle).length !== 2) throw Error('viewer_bundle_patch_mismatch')
  const heightLoop = 'for(let i=0;i<256;i+=16)'
  if (bundle.split(heightLoop).length !== 3) throw Error('viewer_height_patch_mismatch')
  bundle = bundle.replaceAll(heightLoop, 'for(let i=-64;i<320;i+=16)')
  const listen = 's=!0,u.listen(o),o.on("position"'
  if(bundle.split(listen).length!==2)throw Error('viewer_measurement_patch_mismatch')
  bundle = bundle.replace(listen, 's=!0,u.listen(o),o.on("view_sample",async t=>{await u.world.waitForChunksToRender();requestAnimationFrame(()=>requestAnimationFrame(()=>o.emit("view_sample_ack",t)))}),o.on("position"')
  const install = 'u.listen(o),'
  if (bundle.split(install).length !== 2) throw Error('viewer_pixel_patch_mismatch')
  bundle = bundle.replace(install, install + `(${installPixelProbe.toString()})(u,l,o,THREE,${pixelClass.toString()}),`)
  const firstPerson = 'if(void 0!==r&&void 0!==o)return h&&(h.dispose(),h=null),void u.setFirstPersonCamera(t,r,o);'
  if(bundle.split(firstPerson).length!==2)throw Error('viewer_eye_level_patch_mismatch')
  bundle=bundle.replace(firstPerson,'if(new URLSearchParams(location.search).get("view")==="inside")o=0;'+firstPerson)
  app.get('/index.js', (req, res) => res.type('js').send(bundle.replace(needle, cameraFollow)))
  let terrainWorker = fs.readFileSync(require.resolve('prismarine-viewer/public/worker.js'), 'utf8')
  for (const [before, after] of [
    ['i.sections[Math.floor(a/16)]', 'i.sections[Math.floor((a-i.minY)/16)]'],
    ['l.sections[Math.floor(n/16)]', 'l.sections[Math.floor((n-l.minY)/16)]'],
    ['g.position.y<0', 'g.position.y< -64'],
    ['n.position.y<0', 'n.position.y< -64']
  ]) {
    if (terrainWorker.split(before).length !== 2) throw Error('viewer_terrain_patch_mismatch')
    terrainWorker = terrainWorker.replace(before, after)
  }
  app.get('/worker.js', (req, res) => res.type('js').send(terrainWorker))
  setupRoutes(app)
  const io = new Server(http, { allowRequest: (req, callback) => callback(null, req.headers.host === `127.0.0.1:${http.address()?.port}` && allowed(req.headers.origin)) })
  io.on('connection', socket => {
    report('viewer', { connected: true, viewers: io.engine.clientsCount })
    socket.emit('version', bot.version)
    const world = new WorldView(bot.world, 3, bot.entity.position, socket)
    socket.removeAllListeners('mouseClick') // This is a read-only view.
    const failed = () => report('viewer_failed', { error: 'view_stream_failed_bot_work_continues' })
    world.init(bot.entity.position).catch(failed)
    const position = () => {
      socket.emit('position', { pos: bot.entity.position, yaw: bot.entity.yaw, addMesh: true })
      world.updatePosition(bot.entity.position).catch(failed)
    }
    position()
    const timer = setInterval(position, 500)
    let pending=null, sequence=0
    const samples=setInterval(()=>{
      if(pending===null){pending={id:++sequence,at_ms:Date.now()};socket.emit('view_sample',pending)}
    },1000)
    socket.on('view_sample_ack',value=>{
      if(pending&&value?.id===pending.id){
        report('viewer_sample',{age_ms:Date.now()-pending.at_ms,at_ms:Date.now(),scope:'all_pending_meshes_then_two_frames_round_trip'})
        pending=null
      }
    })
    bot.on('move', position)
    world.listenToBot(bot)
    const closeMeasurements = attachPixelMeasurements(bot, socket, report)
    // No blockClicked handler: rendering has no action authority.
    socket.on('disconnect', () => {
      clearInterval(timer)
      clearInterval(samples)
      closeMeasurements()
      bot.removeListener('move', position)
      world.removeListenersFromBot(bot)
      report('viewer', { connected: io.engine.clientsCount > 0, viewers: io.engine.clientsCount })
    })
  })
  await new Promise((resolve, reject) => { http.once('error', reject); http.listen(port, '127.0.0.1', resolve) })
  return { url: `http://127.0.0.1:${http.address().port}`, close: () => new Promise(resolve => io.close(resolve)) }
}
module.exports = { openViewer }
