"""Bounded asynchronous event retention; direct control never waits on disk."""
import json
import queue
import threading


class RuntimeEvents:
    def __init__(self, path):
        self.path = path
        self.queue = queue.Queue(maxsize=256)
        self.failed = False
        self.closed = False
        self.thread = threading.Thread(target=self._write, daemon=True, name="profile-evidence")
        self.thread.start()

    def put(self, record):
        if self.closed:
            self.failed = True
            return
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.failed = True

    def _write(self):
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                with self.path.open("a") as stream:
                    stream.write(json.dumps(item, allow_nan=False)+"\n")
            except Exception:
                self.failed = True
            finally:
                self.queue.task_done()

    def close(self, timeout=1):
        if not self.closed:
            self.closed = True
            try:
                self.queue.put_nowait(None)
            except queue.Full:
                self.failed = True
        self.thread.join(timeout)
        return not self.thread.is_alive() and not self.failed
