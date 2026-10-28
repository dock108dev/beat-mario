const test = require('node:test')
const assert = require('node:assert/strict')
const { Scheduler } = require('../scheduler.cjs')
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const req = (id, revision = 0, timeout_ms = 1000) => ({ request_id: id, revision, timeout_ms, args: {} })

test('Stop cancels active and queued actions and rejects stale authority', async () => {
  const events = [], ran = []
  const s = new Scheduler({ halt () {}, emit: (...e) => events.push(e), run: async (args, signal) => {
    ran.push(1)
    await new Promise(resolve => signal.addEventListener('abort', resolve, { once: true }))
  } })
  s.submit(req('active')); s.submit(req('queued'))
  assert.equal(await s.cancel(), 1)
  assert.equal(s.active, null)
  assert.equal(s.queue.length, 0)
  assert.equal(ran.length, 1)
  assert.throws(() => s.submit(req('late')), /stale_revision/)
  assert(events.some(e => e[0] === 'failed' && e[1].request_id === 'queued'))
  assert(!events.some(e => e[0] === 'completed'))
})

test('Deadline abort releases action ownership without completing', async () => {
  const events = []
  const s = new Scheduler({ halt () {}, emit: (...e) => events.push(e), run: async (args, signal) => {
    await new Promise(resolve => signal.addEventListener('abort', resolve, { once: true }))
  } })
  s.submit(req('timeout', 0, 20))
  await pause(60)
  assert.equal(s.active, null)
  assert(events.some(e => e[0] === 'failed' && e[2].error === 'deadline_exceeded'))
})

test('Queue is serialized and queue waiting consumes the deadline', async () => {
  const events = []; let count = 0, maximum = 0
  const s = new Scheduler({ halt () {}, emit: (...e) => events.push(e), run: async () => {
    maximum = Math.max(maximum, ++count); await pause(30); count--; return {}
  } })
  s.submit(req('one')); s.submit(req('expired', 0, 10)); s.submit(req('three'))
  await pause(100)
  assert.equal(maximum, 1)
  assert(events.some(e => e[1].request_id === 'expired' && e[2].error === 'deadline_exceeded'))
  assert.equal(events.filter(e => e[0] === 'completed').length, 2)
})

test('Cancellation barrier rejects a new revision until action settles', async () => {
  const s = new Scheduler({ halt () {}, emit () {}, run: async (args, signal) => {
    await new Promise(resolve => signal.addEventListener('abort', () => setTimeout(resolve, 20), { once: true }))
  } })
  s.submit(req('one'))
  const stopped = s.cancel()
  assert.throws(() => s.submit(req('new', 1)), /stale_revision/)
  await stopped
  assert.equal(s.stopping, false)
})

test('An action that ignores abort closes its connection and cannot release queued work', async () => {
  let closed = false
  const events = []
  const s = new Scheduler({ halt () {}, emit: (...e) => events.push(e), failClosed: () => { closed = true }, run: () => new Promise(() => {}) })
  s.submit(req('hung', 0, 10)); s.submit(req('queued'))
  await pause(1650)
  assert(closed)
  assert(s.blocked && s.stopping)
  assert(!events.some(e => e[1].request_id === 'queued' && e[0] === 'progress'))
  assert.throws(() => s.submit(req('late', s.revision)), /stale_revision/)
})
