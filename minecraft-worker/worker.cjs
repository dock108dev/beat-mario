'use strict'
const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')
const { Scheduler } = require('./scheduler.cjs')
const { LOGS, inside, regionsOf, resources, safeTarget, chooseTool, visibleFrom, stands, multiChanges, goalGuard } = require('./resource-skills.cjs')
const { openViewer } = require('./viewer.cjs')
// stdout is exclusively JSONL. Do not forward game/chat/authentication text.
console.log = () => {}
const VERSION = '1.21.4'
let bot, viewer, scheduler, session = null, ready = false, lifecycleBusy = false, stopBusy = false
let worldId = 'unknown'
let sequence = 0, viewerClients = 0
const usedSessions = new Set()
const requests = new Set()
const emit = (type, request, data = {}) => process.stdout.write(JSON.stringify({ v: 1, seq: ++sequence, at_ms: Date.now(), session_id: request?.session_id ?? session, request_id: request?.request_id ?? null, type, ...data }) + '\n')
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
const position = () => bot?.entity?.position?.clone()
function observe () {
  const p = position()
  return {
    ready, world_id: worldId, game_mode: bot?.game?.gameMode, revision: scheduler?.revision ?? 0, character: bot?.username, game_version: VERSION,
    position: p, yaw: bot?.entity?.yaw, health: bot?.health, food: bot?.food, dimension: bot?.game?.dimension,
    active: scheduler?.active?.request.request_id ?? null, queued: scheduler?.queue.length ?? 0,
    held_item: bot?.heldItem?.name ?? null,
    inventory: bot?.inventory?.items().map(i => ({ name: i.name, count: i.count, slot: i.slot })) ?? [],
    entities: Object.values(bot?.players ?? {}).filter(v => v.entity && v.username !== bot.username).slice(0, 16).map(v => ({ name: v.username, id: v.entity.id, position: v.entity.position })),
    players: Object.keys(bot?.players ?? {}), viewer_url: viewer?.url ?? null, viewer_clients: viewerClients,
    resources: ready && p ? resources(bot) : [],
    drops: Object.values(bot?.entities ?? {}).filter(e => e.name === 'item' && e.position.distanceTo(p) < 32).slice(0, 32).map(e => ({ id: e.id, position: e.position, item: e.getDroppedItem?.()?.name })),
    nearby_blocks: p ? [new Vec3(0, -1, 0), new Vec3(1, -1, 0), new Vec3(0, 0, 1)].map(d => bot.blockAt(p.floored().plus(d))).filter(Boolean).map(b => ({ name: b.name, position: b.position })) : []
  }
}
function haltBot (target) {
  target?.pathfinder?.setGoal(null)
  target?.clearControlStates()
  target?.stopDigging()
}
function halt () { haltBot(bot) }
function validNumber (n) { return typeof n === 'number' && Number.isFinite(n) }
function targetOf (args) {
  if (!args.target || !['x', 'y', 'z'].every(k => validNumber(args.target[k]))) throw Error('invalid_target')
  const target = new Vec3(args.target.x, args.target.y, args.target.z)
  if (target.distanceTo(position()) > 32) throw Error('target_out_of_bounds')
  return target
}
function followEntity (args) {
  if (typeof args.player !== 'string' || !Number.isInteger(args.entity_id) || !Number.isInteger(args.duration_ms) || args.duration_ms < 1000 || args.duration_ms > 25000) throw Error('invalid_follow')
  const entity = bot?.players[args.player]?.entity
  if (!entity || entity.id !== args.entity_id || args.player === bot.username) throw Error('follow_player_disappeared')
  if (entity.position.distanceTo(position()) > 32) throw Error('follow_distance_limit')
  return entity
}
async function run (args, signal) {
  const local = bot
  const before = observe()
  const abort = () => haltBot(local)
  signal.addEventListener('abort', abort, { once: true })
  let violation = null
  const guard = setInterval(() => {
    violation = violation || goalGuard(local, args, worldId)
    if (violation) haltBot(local)
  }, 100)
  try {
    signal.throwIfAborted()
    violation = goalGuard(local, args, worldId)
    if (violation) throw Error(violation)
    if (args.world && JSON.stringify(args.world) !== JSON.stringify([worldId, local.game.dimension, VERSION])) throw Error('stale_world')
    const regions = regionsOf(args.protected)
    const movements = local.pathfinder.movements
    movements.exclusionAreasStep = [b => inside(b.position || b, regions) ? 100 : 0]
    if (before.health <= 6 || before.food <= 4) throw Error('survival_health_or_food_limit')
    if (args.action === 'follow') {
      const entity = followEntity(args)
      const origin = position()
      let lastProgress = Date.now(), lastPosition = position(), samples = 0
      local.pathfinder.setGoal(new goals.GoalFollow(entity, 2), true)
      const deadline = Date.now() + args.duration_ms
      while (Date.now() < deadline) {
        signal.throwIfAborted()
        const current = followEntity(args)
        if (position().distanceTo(origin) > 32 || current.position.distanceTo(origin) > 32) throw Error('follow_distance_limit')
        if (position().distanceTo(lastPosition) > 0.25 || position().distanceTo(current.position) < 3) {
          lastProgress = Date.now(); lastPosition = position()
        }
        if (Date.now() - lastProgress > 5000) throw Error('follow_obstructed')
        samples++
        await delay(100)
      }
      signal.throwIfAborted()
      return { before: before.position, after: position(), observed: 'player_tracking', player: args.player, samples }
    }
    let target = targetOf(args)
    safeTarget(local, target, regions)
    if (args.action === 'approach') {
      const recovery = []
      if (!visibleFrom(local, position(), target)) {
        let arrived = false
        for (const stand of stands(local, target, regions).filter(p => !args.goal_origin || p.distanceTo(new Vec3(args.goal_origin.x,args.goal_origin.y,args.goal_origin.z)) <= 32).slice(0, 3)) {
          signal.throwIfAborted()
          try {
            await local.pathfinder.goto(new goals.GoalBlock(stand.x, stand.y, stand.z))
            if (visibleFrom(local, position(), target)) { arrived = true; break }
          } catch (error) { signal.throwIfAborted(); recovery.push({stand, reason:error.message}) }
        }
        if (!arrived) throw Error('resource_approach_obstructed: ' + recovery.map(r=>r.reason).join('; '))
      }
      return { observed: 'reachable_block', target, position: position(), recovery }
    }
    if (args.action === 'pickup') {
      // Drops move while falling: resolve the observed entity again before routing.
      await delay(800)
      signal.throwIfAborted()
      const drop = Object.values(local.entities).filter(e => e.name === 'item' && (args.entity_id ? e.id === args.entity_id : e.position.distanceTo(target) < 5)).sort((a,b)=>a.position.distanceTo(target)-b.position.distanceTo(target))[0]
      if (!drop) return { observed: 'drop_no_longer_present', inventory: observe().inventory }
      target = drop.position.clone()
      safeTarget(local, target, regions)
    }
    if (args.action === 'move' || args.action === 'pickup') {
      const radius = 1
      await local.pathfinder.goto(new goals.GoalNear(target.x, target.y, target.z, radius))
      signal.throwIfAborted()
      if (position().distanceTo(target) > 1.8) throw Error('movement_not_observed')
      if (args.action === 'pickup') await delay(700)
      signal.throwIfAborted()
      return { before: before.position, after: position(), observed: 'position', inventory: observe().inventory }
    }
    if (args.action === 'equip') {
      const block = local.blockAt(target.floored())
      if (!block || block.name !== args.expected) throw Error('resource_changed')
      const tool = chooseTool(local, block)
      if (tool) await local.equip(tool, 'hand')
      else await local.unequip('hand')
      signal.throwIfAborted()
      return { observed: 'equipment', tool: local.heldItem?.name || 'hand', hand_valid: true }
    }
    if (args.action === 'dig') {
      const block = local.blockAt(target.floored())
      if (!block || block.name === 'air' || block.name === 'bedrock' || target.distanceTo(position()) > 4.5) throw Error('block_not_reachable')
      if (args.expected && (block.name !== args.expected || !LOGS.includes(block.name))) throw Error('resource_changed')
      if (args.expected && local.inventory.emptySlotCount() === 0 && !local.inventory.items().some(i => i.name === block.name && i.count < i.stackSize)) throw Error('inventory_full')
      if (args.expected && !visibleFrom(local, position(), target.floored())) throw Error('resource_line_of_sight_blocked')
      if (args.expected && target.y < Math.floor(position().y)) throw Error('unsafe_dig_position')
      // Mineflayer predicts block removal locally. Require the SERVER packet too.
      let serverState = null
      const changed = packet => {
        if (packet.location.x === block.position.x && packet.location.y === block.position.y && packet.location.z === block.position.z) serverState = packet.type
      }
      const multiChanged = packet => multiChanges(packet).forEach(changed)
      local._client.on('block_change', changed)
      local._client.on('multi_block_change', multiChanged)
      try {
        await local.lookAt(block.position.offset(0.5, 0.5, 0.5), true)
        signal.throwIfAborted()
        await local.dig(block, 'ignore')
        const deadline = Date.now() + 3000
        while (!signal.aborted && Date.now() < deadline && (serverState === null || serverState === block.stateId)) await delay(25)
        signal.throwIfAborted()
        const after = local.blockAt(block.position)
        if (serverState === null || serverState === block.stateId || !after || after.type === block.type) throw Error('server_block_change_not_observed')
        return { position: block.position, before: block.name, after: after.name, server_state_id: serverState, observed: 'server_block_change' }
      } finally { local._client.removeListener('block_change', changed); local._client.removeListener('multi_block_change', multiChanged) }
    }
    throw Error('unsupported_action')
  } finally {
    clearInterval(guard)
    signal.removeEventListener('abort', abort)
    haltBot(local)
    if (violation) throw Error(violation)
  }
}
async function disconnect () {
  ready = false
  if (scheduler) {
    try { await scheduler.cancel() } catch { halt() }
  }
  if (viewer) { const old = viewer; viewer = null; await old.close() }
  if (bot) {
    const old = bot
    bot = null
    old.quit()
    if (!old._client.ended) await Promise.race([new Promise(resolve => old.once('end', resolve)), delay(1000)])
    if (!old._client.ended) old._client.end()
  }
  scheduler = null
  viewerClients = 0
  session = null
}
async function connect (request) {
  const args = request.args ?? {}
  if (usedSessions.has(request.session_id)) throw Error('session_already_used')
  if (session) throw Error('disconnect_required')
  if (!Number.isInteger(args.port) || args.port < 1024 || args.port > 65535) throw Error('invalid_port')
  if (!Number.isInteger(args.viewer_port ?? 0) || (args.viewer_port ?? 0) < 0 || (args.viewer_port ?? 0) > 65535) throw Error('invalid_viewer_port')
  usedSessions.add(request.session_id)
  session = request.session_id
  worldId = typeof args.world_id === 'string' ? args.world_id : 'unknown'
  bot = mineflayer.createBot({ host: '127.0.0.1', port: args.port, username: 'CompanionBot', auth: 'offline', version: VERSION, hideErrors: true, checkTimeoutInterval: 60000 })
  const local = bot
  local.loadPlugin(pathfinder)
  local.on('error', error => emit('connection_error', null, { error: error.message?.startsWith('client timed out') ? 'keepalive_timeout' : 'game_connection_error' }))
  local.on('end', () => {
    if (bot !== local) return
    ready = false
    scheduler?.cancel().catch(() => {})
    emit('disconnected', null, { reason: 'game_connection_ended' })
  })
  let timer
  const connectDeadline = Date.now() + request.timeout_ms
  try {
    await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(Error('connect_timeout')), request.timeout_ms)
      local.once('spawn', resolve)
      local.once('end', () => reject(Error('connection_ended_before_ready')))
      local.once('error', () => reject(Error('connection_failed')))
    })
    clearTimeout(timer)
    await Promise.race([
      local.waitForChunksToLoad(),
      new Promise((resolve, reject) => { timer = setTimeout(() => reject(Error('connect_timeout')), Math.max(1, connectDeadline - Date.now())) })
    ])
    if (local._client.ended) throw Error('connection_ended_before_ready')
    const movements = new Movements(local)
    movements.canDig = false
    movements.allow1by1towers = false
    movements.allowParkour = false
    movements.allowFreeMotion = false
    movements.scafoldingBlocks = []
    local.pathfinder.setMovements(movements)
    scheduler = new Scheduler({ run, halt, emit, failClosed: () => { ready = false; local.end() } })
    ready = true
    try {
      viewer = await openViewer(local, session, args.viewer_port ?? 0, (type, data) => { if (type === 'viewer') viewerClients = data.viewers; emit(type, null, data) })
    } catch {
      emit('viewer_failed', request, { error: 'viewer_unavailable_bot_remains_connected' })
    }
    return observe()
  } catch (error) { await disconnect(); throw error } finally { clearTimeout(timer) }
}
async function handle (request) {
  try {
    if (!request || request.v !== 1 || typeof request.request_id !== 'string' || typeof request.session_id !== 'string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(request.request_id ?? '') || !/^[a-zA-Z0-9_-]{1,80}$/.test(request.session_id ?? '')) throw Error('invalid_envelope')
    if (requests.has(request.request_id)) throw Error('duplicate_request')
    if (requests.size >= 10000) throw Error('worker_request_budget_restart_required')
    requests.add(request.request_id)
    if (!Number.isInteger(request.timeout_ms) || request.timeout_ms < 100 || request.timeout_ms > 30000) throw Error('invalid_timeout')
    if (request.op === 'connect') {
      if (lifecycleBusy) throw Error('lifecycle_busy')
      lifecycleBusy = true
      try { emit('completed', request, { result: await connect(request) }) } finally { lifecycleBusy = false }
      return
    }
    if (!session || request.session_id !== session) throw Error('stale_session')
    if (request.op === 'disconnect') {
      if (lifecycleBusy) throw Error('lifecycle_busy')
      lifecycleBusy = true
      try { await disconnect(); emit('completed', request, { result: { disconnected: true } }) } finally { lifecycleBusy = false }
      return
    }
    if (lifecycleBusy || !ready) throw Error('not_ready')
    if (request.op === 'observe' || request.op === 'capabilities') {
      emit('completed', request, { result: request.op === 'observe' ? observe() : { actions: ['move', 'dig', 'follow', 'approach', 'equip', 'pickup'], protocol: 1, max_distance: 32, max_timeout_ms: 30000 } })
    } else if (request.op === 'execute') {
      if (!['move', 'dig', 'follow', 'approach', 'equip', 'pickup'].includes(request.args?.action)) throw Error('unsupported_action')
      if (request.args.action === 'follow') followEntity(request.args)
      else targetOf(request.args)
      if (stopBusy) throw Error('stop_in_progress')
      scheduler.submit(request)
    } else if (request.op === 'cancel') {
      if (stopBusy) throw Error('stop_in_progress')
      stopBusy = true
      emit('cancel_dispatched', request)
      try {
      await scheduler.cancel()
      let p = position(), stableSince = Date.now(), stationary = false
      const stopDeadline = Date.now() + 1500
      while (ready && p && Date.now() < stopDeadline) {
        await delay(100)
        const current = position()
        if (!current || current.distanceTo(p) >= 0.01) stableSince = Date.now()
        p = current
        if (Date.now() - stableSince >= 300) { stationary = true; break }
      }
      emit('completed', request, { result: { revision: scheduler.revision, controls_cleared: true, stopped_observed: !!stationary, confirmation: stationary ? 'stationary_position_observed' : 'unconfirmed', position: position() } })
      } finally { stopBusy = false }
    } else throw Error('unknown_operation')
  } catch (error) { emit('failed', request, { error: error.message || 'operation_failed' }) }
}
let input = ''
// Bound the frame before parsing; readline alone can accumulate unbounded input.
process.stdin.setEncoding('utf8')
process.stdin.on('data', chunk => {
  input += chunk
  if (input.length > 65536) return shutdown()
  let end
  while ((end = input.indexOf('\n')) !== -1) {
    const line = input.slice(0, end); input = input.slice(end + 1)
    try { void handle(JSON.parse(line)) } catch { emit('failed', null, { error: 'invalid_json' }) }
  }
})
let shuttingDown = false
async function shutdown () {
  if (shuttingDown) return
  shuttingDown = true
  const forced = setTimeout(() => process.exit(1), 4000)
  await disconnect()
  clearTimeout(forced)
  process.exit(0)
}
process.stdin.on('end', shutdown)
process.on('SIGTERM', shutdown)
process.on('SIGINT', shutdown)
setInterval(() => { if (ready) emit('state', null, { result: observe() }) }, 500).unref()
emit('worker_ready', null, { protocol: 1, node: process.version, game_version: VERSION })
