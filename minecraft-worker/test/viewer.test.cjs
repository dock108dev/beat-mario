const test = require('node:test')
const assert = require('node:assert/strict')
const { Script } = require('node:vm')
const { openViewer } = require('../viewer.cjs')

test('Viewer serves valid height-corrected bundles, identifies session, and rejects foreign origins/hosts', async () => {
  const viewer = await openViewer({ username: 'CompanionBot' }, 'viewer-test', 0, () => {})
  try {
    assert(viewer.url.startsWith('http://127.0.0.1:'))
    assert.equal((await (await fetch(viewer.url + '/session')).json()).session_id, 'viewer-test')
    assert.equal((await fetch(viewer.url, { headers: { Origin: 'https://untrusted.example' } })).status, 403)
    const wrongHost = await new Promise((resolve, reject) => {
      require('node:http').get(viewer.url, { headers: { Host: 'untrusted.example' } }, response => { response.resume(); resolve(response.statusCode) }).on('error', reject)
    })
    assert.equal(wrongHost, 403)
    const browser = await (await fetch(viewer.url + '/index.js')).text()
    const terrain = await (await fetch(viewer.url + '/worker.js')).text()
    new Script(browser)
    new Script(terrain)
    assert(browser.includes('for(let i=-64;i<320;i+=16)'))
    assert(terrain.includes('i.sections[Math.floor((a-i.minY)/16)]'))
    assert(!browser.includes('t.y>0&&s&&(h.target.set'))
  } finally { await viewer.close() }
})
