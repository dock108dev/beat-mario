'use strict'
// Opt-in read-only measurement: classify real framebuffer pixels at a world face.
function pixelClass (rgb) {
  if (!Array.isArray(rgb) || rgb.length !== 3 || !rgb.every(v => Number.isFinite(v) && v >= 0 && v <= 255)) return null
  const [r, g, b] = rgb
  if (Math.min(r, g, b) > 75 && Math.max(r, g, b) - Math.min(r, g, b) < 18) return 'white_wool'
  if (r > 30 && r > g * 1.18 && g > b * 1.15) return 'dirt'
  return null
}
function installPixelProbe (viewer, renderer, socket, THREE, classify) {
  const raw = new URLSearchParams(location.search).get('measure')
  if (!raw) return
  const coords = raw.split(',').map(Number)
  if (coords.length !== 3 || !coords.every(Number.isInteger)) return
  const position = { x: coords[0], y: coords[1], z: coords[2] }
  const target = new THREE.Vector3(position.x + 0.5, position.y + 1.001, position.z + 0.5)
  const ray = new THREE.Raycaster()
  let pending = null, previous = null, clock = null, baselineSent = false
  socket.on('measurement_clock', message => {
    const received = Date.now(), rtt = received - message.client_ms
    if (rtt >= 0 && (!clock || rtt < clock.rtt_ms)) clock = { rtt_ms: rtt, offset_ms: message.server_ms - (received + message.client_ms) / 2, uncertainty_ms: rtt / 2 + 1 }
  })
  for (let i = 0; i < 5; i++) setTimeout(() => socket.emit('measurement_clock', { client_ms: Date.now() }), i * 200)
  socket.emit('pixel_watch', position)
  socket.on('pixel_change', change => {
    pending = { ...change, before: previous, received_ms: Date.now() }
  })
  const render = renderer.render.bind(renderer)
  renderer.render = function (...args) {
    const result = render(...args)
    const rect = renderer.domElement.getBoundingClientRect()
    if (document.visibilityState !== 'visible' || rect.width <= 0 || rect.height <= 0) return result
    const ndc = target.clone().project(viewer.camera)
    if (Math.abs(ndc.x) >= 0.98 || Math.abs(ndc.y) >= 0.98 || ndc.z < -1 || ndc.z > 1) return result
    ray.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), viewer.camera)
    const hit = ray.intersectObjects(Object.values(viewer.world.sectionMeshs), false)[0]
    if (!hit || !hit.face) return result
    const inside = hit.point.clone().addScaledVector(hit.face.normal, -0.001)
    if (Math.floor(inside.x) !== position.x || Math.floor(inside.y) !== position.y || Math.floor(inside.z) !== position.z) return result
    const gl = renderer.getContext(), w = gl.drawingBufferWidth, h = gl.drawingBufferHeight
    const x = Math.floor((ndc.x + 1) * w / 2), y = Math.floor((ndc.y + 1) * h / 2)
    if (x < 1 || y < 1 || x >= w - 1 || y >= h - 1) return result
    const pixels = new Uint8Array(36), rgb = [0, 0, 0]
    gl.readPixels(x - 1, y - 1, 3, 3, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
    for (let i = 0; i < 9; i++) for (let c = 0; c < 3; c++) rgb[c] += pixels[i * 4 + c] / 9
    const material = classify(rgb), at = Date.now()
    if (pending && clock && material === pending.after && pending.before?.material === pending.before_name && pending.before.material !== material) {
      socket.emit('pixel_observed', { id: pending.id, frame_ms: at, rgb, before_rgb: pending.before.rgb, material, before_material: pending.before.material, pixel: { x, y, width: w, height: h }, clock, position })
      pending = null
    }
    if (pending && at - pending.received_ms > 10000) {
      socket.emit('pixel_missed', { id: pending.id, reason: 'No matched visible pixel transition within ten seconds' })
      pending = null
    }
    if (!baselineSent && material) {
      socket.emit('pixel_baseline', { material, rgb, position })
      baselineSent = true
    }
    previous = { material, rgb, frame_ms: at }
    return result
  }
}
function attachPixelMeasurements (bot, socket, report) {
  let watch = null, pending = null, sequence = 0
  socket.on('measurement_clock', value => {
    if (Number.isFinite(value?.client_ms)) socket.emit('measurement_clock', { client_ms: value.client_ms, server_ms: Date.now() })
  })
  socket.on('pixel_watch', p => {
    if (!p || !['x', 'y', 'z'].every(k => Number.isInteger(p[k])) || Math.abs(p.x) > 30000000 || Math.abs(p.z) > 30000000 || p.y < -64 || p.y > 319) return
    watch = { x: p.x, y: p.y, z: p.z }
    report('viewer_pixel_watch', { position: watch })
  })
  socket.on('pixel_baseline', value => {
    if (watch && value?.position && ['x','y','z'].every(k => value.position[k] === watch[k]) && Array.isArray(value.rgb) && pixelClass(value.rgb) === value.material) report('viewer_pixel_baseline', { position: watch, material: value.material, rgb: value.rgb })
  })
  const changed = (before, after) => {
    if (!watch || !before || !after || !['x', 'y', 'z'].every(k => after.position[k] === watch[k])) return
    if (!['white_wool', 'dirt'].includes(after.name) || after.name === before.name) return
    pending = { id: ++sequence, position: watch, before_name: before.name, after: after.name, observed_server_ms: Date.now() }
    report('viewer_pixel_change', pending)
    socket.emit('pixel_change', pending)
  }
  bot.on('blockUpdate', changed)
  socket.on('pixel_observed', value => {
    if (!pending || value?.id !== pending.id || value.material !== pending.after || value.before_material !== pending.before_name) return
    if (!Array.isArray(value.rgb) || value.rgb.length !== 3 || !value.rgb.every(Number.isFinite) || pixelClass(value.rgb) !== pending.after) return
    if (pixelClass(value.before_rgb) !== pending.before_name || !Number.isFinite(value.frame_ms)) return
    if (!value.position || !['x', 'y', 'z'].every(k => value.position[k] === watch[k])) return
    const pixel = value.pixel, clock = value.clock
    if (!pixel || !['x', 'y', 'width', 'height'].every(k => Number.isInteger(pixel[k])) || pixel.x < 0 || pixel.y < 0 || pixel.x >= pixel.width || pixel.y >= pixel.height) return
    if (!clock || !['rtt_ms', 'offset_ms', 'uncertainty_ms'].every(k => Number.isFinite(clock[k])) || clock.rtt_ms < 0 || clock.uncertainty_ms < clock.rtt_ms / 2 + 1) return
    const received = Date.now()
    report('viewer_pixel_observed', { ...pending, frame_ms: value.frame_ms, rgb: value.rgb, before_rgb: value.before_rgb, material: value.material, before_material: value.before_material, pixel: value.pixel, clock: value.clock, ack_server_ms: received, observed_change_to_ack_upper_ms: received - pending.observed_server_ms, scope: 'Matched old/new framebuffer colors at ray-verified world face; excludes unknown server-commit-to-bot-observation delay' })
    pending = null
  })
  socket.on('pixel_missed', value => {
    if (!pending || value?.id !== pending.id) return
    report('viewer_pixel_missed', { ...pending, reason: 'No matched visible framebuffer transition' })
    pending = null
  })
  return () => bot.removeListener('blockUpdate', changed)
}
module.exports = { pixelClass, installPixelProbe, attachPixelMeasurements }
