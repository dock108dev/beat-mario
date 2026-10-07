"""Release only an explicitly registered child process group when its owner dies."""
import json
import os
import signal
import subprocess
import sys


def identity(pid):
    return subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='], capture_output=True, text=True, timeout=2).stdout.strip()


class ChildWatchdog:
    def __init__(self, child):
        from smb3_agent.app_runtime import helper_command
        self.process = subprocess.Popen(helper_command('smb3_agent.process_watchdog', '--worker'), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        record = {'pid': child.pid, 'started': identity(child.pid)}
        if not record['started']:
            self.close()
            return
        self.process.stdin.write((json.dumps(record) + '\n').encode())
        self.process.stdin.flush()

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        self.process.wait(timeout=5)


def _worker():
    record = json.loads(sys.stdin.readline())
    sys.stdin.read()  # EOF arrives independently of the parent's cleanup path.
    pid = record['pid']
    if type(pid) is int and pid > 1 and record['started'] and identity(pid) == record['started'] and os.getpgid(pid) == pid:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


if __name__ == '__main__':
    _worker()
