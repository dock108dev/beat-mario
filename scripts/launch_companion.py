"""Launch or stop only this repository's identified personal delivery."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import webbrowser

from smb3_agent.beta_readiness import source_identity

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8765'


def inspect():
    try:
        with urlopen(URL + '/api/delivery', timeout=2) as response:
            result = json.load(response)
        if result.get('schema') != 'game-companion-delivery/v1' or result.get('root') != str(ROOT):
            raise RuntimeError('Port 8765 belongs to another delivery. No process was stopped.')
        return result
    except HTTPError as exc:
        raise RuntimeError('Port 8765 is occupied by an unidentified server. Inspect it before closing it.') from exc
    except URLError:
        return None
    except (ValueError, KeyError) as exc:
        raise RuntimeError('Port 8765 did not provide a valid delivery identity. No process was stopped.') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    current = inspect()
    if args.status:
        print(json.dumps(current or {'running': False}, indent=2))
        return
    if args.stop:
        if not current:
            print('Game Companion is already stopped.')
            return
        token = current["csrf_token"]
        data = urlencode({'csrf_token': token, 'instance': current['instance']}).encode()
        with urlopen(Request(URL + '/api/delivery/shutdown', data=data), timeout=60) as response:
            json.load(response)
        for _ in range(100):
            with socket.socket() as probe:
                probe.settimeout(1)
                closed = probe.connect_ex(('127.0.0.1', 8765)) != 0
            if closed:
                print('Game Companion stopped. Task-owned games were closed; retained history remains on disk.')
                return
            time.sleep(.1)
        raise RuntimeError('Shutdown is not confirmed. Inspect artifacts/local-companion.log; do not assume input or games stopped.')
    expected = source_identity(ROOT)['source_sha256']
    if current and current['source_sha256'] != expected:
        raise RuntimeError('The running delivery uses different source. Use Stop Game Companion.command, then reopen.')
    if not current:
        log = ROOT / 'artifacts/local-companion.log'
        log.parent.mkdir(exist_ok=True)
        with log.open('ab') as stream:
            process = subprocess.Popen([sys.executable, '-m', 'smb3_agent', 'lab', 'ui', '--host', '127.0.0.1', '--port', '8765'],
                                       cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(100):
            current = inspect()
            if current:
                if current['pid'] != process.pid or current['source_sha256'] != expected:
                    raise RuntimeError('A different process took the port. Launch identity could not be confirmed.')
                break
            if process.poll() is not None:
                raise RuntimeError(f'Companion did not start. Check local dependencies and {log}')
            time.sleep(.1)
        else:
            raise RuntimeError(f'Launch is not confirmed. Inspect {log}')
    if not args.no_browser:
        webbrowser.open(URL)
    print(f'Game Companion: {URL}\nSource: {expected}\nOpening never grants gameplay control.')
    print('Closing the browser does not stop execution. Use Stop Game Companion.command to stop this delivery and its games.')


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
