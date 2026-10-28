'use strict'
// The sole owner of gameplay actions. Revisions are cancellation authority.
class Scheduler {
  constructor ({ run, halt, emit, failClosed = () => {} }) {
    Object.assign(this, { run, halt, emit, failClosed })
    this.revision = 0
    this.queue = []
    this.active = null
    this.stopping = false
    this.blocked = false
  }

  submit (request) {
    if (this.stopping || request.revision !== this.revision) throw Error('stale_revision')
    if (this.queue.length >= 16) throw Error('queue_full')
    const work = { request, controller: new AbortController(), deadline: Date.now() + request.timeout_ms }
    this.queue.push(work)
    this.emit('accepted', request, { revision: this.revision })
    this.pump()
  }

  async pump () {
    if (this.active || this.stopping || !this.queue.length) return
    const work = this.active = this.queue.shift()
    const { request, controller } = work
    let timer, watchdog
    try {
      if (Date.now() >= work.deadline) throw Error('deadline_exceeded')
      this.emit('progress', request, { phase: 'started' })
      timer = setTimeout(() => controller.abort('deadline_exceeded'), work.deadline - Date.now())
      const result = await Promise.race([
        this.run(request.args, controller.signal),
        new Promise((resolve, reject) => {
          const quarantine = () => {
            watchdog = setTimeout(() => {
              this.blocked = this.stopping = true
              this.halt()
              for (const queued of this.queue.splice(0)) this.emit('failed', queued.request, { error: 'connection_closed_after_timeout' })
              this.failClosed()
              reject(Error('action_abort_unconfirmed_connection_closed'))
            }, 1500)
          }
          controller.signal.addEventListener('abort', quarantine, { once: true })
        })
      ])
      if (controller.signal.aborted || request.revision !== this.revision) throw Error('canceled')
      this.emit('completed', request, { result })
    } catch (error) {
      this.emit('failed', request, { error: controller.signal.reason || error.message })
    } finally {
      clearTimeout(timer)
      clearTimeout(watchdog)
      this.active = null
      work.resolve?.()
      this.pump()
    }
  }

  async cancel () {
    if (this.stopping) throw Error('stop_in_progress')
    this.stopping = true
    this.revision++ // Advance before any await; slow producers lose authority immediately.
    const active = this.active
    for (const work of this.queue.splice(0)) this.emit('failed', work.request, { error: 'canceled_queued' })
    active?.controller.abort('canceled')
    this.halt()
    try {
      if (active) {
        let timer
        try {
          await Promise.race([
            new Promise(resolve => { active.resolve = resolve }),
            new Promise((resolve, reject) => { timer = setTimeout(() => reject(Error('stop_unconfirmed')), 2000) })
          ])
        } finally { clearTimeout(timer) }
      }
      return this.revision
    } finally {
      // A stuck operation keeps the scheduler closed until the connection is destroyed.
      if (!this.active && !this.blocked) this.stopping = false
    }
  }
}
module.exports = { Scheduler }
