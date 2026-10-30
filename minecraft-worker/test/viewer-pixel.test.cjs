const test = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const { pixelClass, attachPixelMeasurements } = require('../viewer-pixel.cjs')

test('Pixel classification rejects invalid measurements', () => {
  for (const value of [null, [], [255, 255], [Infinity, 0, 0], [300, 300, 300], [-1, 0, 0]]) assert.equal(pixelClass(value), null)
  assert.equal(pixelClass([250, 252, 253]), 'white_wool')
  assert.equal(pixelClass([143, 101, 69]), 'dirt')
  assert.equal(pixelClass([10, 150, 200]), null)
})

test('Only matching real changes with valid old/new pixels are acknowledged; listeners are released', () => {
  const bot = new EventEmitter()
  const socket = new EventEmitter()
  const reports = []
  const cleanup = attachPixelMeasurements(bot, socket, (type, value) => reports.push({ type, ...value }))
  const position = { x: 10, y: 20, z: 30 }
  socket.emit('pixel_watch', position)
  const before = { name: 'white_wool', position }
  bot.emit('blockUpdate', before, { name: 'dirt', position: { ...position, x: 11 } })
  assert(!reports.some(r => r.type === 'viewer_pixel_change'))
  bot.emit('blockUpdate', before, { name: 'dirt', position })
  const ack = { id: 1, material: 'dirt', before_material: 'white_wool', rgb: [143, 101, 69], before_rgb: [250, 252, 253], frame_ms: Date.now(), position,
    pixel: { x: 3, y: 3, width: 10, height: 10 }, clock: { rtt_ms: 2, offset_ms: 0, uncertainty_ms: 2 } }
  socket.emit('pixel_missed', { id: 999 }) // A stale miss must not discard the new change.
  for (const bad of [{ id: 999 }, { before_rgb: [143, 101, 69] }, { position: { ...position, x: 11 } }, { clock: { rtt_ms: 2, offset_ms: 0, uncertainty_ms: 0 } }, { pixel: { x: 10, y: 3, width: 10, height: 10 } }]) socket.emit('pixel_observed', { ...ack, ...bad })
  assert(!reports.some(r => r.type === 'viewer_pixel_observed'))
  socket.emit('pixel_observed', ack)
  socket.emit('pixel_observed', ack)
  assert.equal(reports.filter(r => r.type === 'viewer_pixel_observed').length, 1)
  assert.equal(bot.listenerCount('blockUpdate'), 1)
  cleanup()
  assert.equal(bot.listenerCount('blockUpdate'), 0)
})
