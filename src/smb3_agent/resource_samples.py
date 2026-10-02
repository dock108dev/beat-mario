"""Read-only local resource measurements, separate from control and GPU estimates."""
import json
import os
import subprocess
import threading
import time
import urllib.request


class ResourceSamples:
    def __init__(self, runtime):
        self.runtime = runtime
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample,daemon=True,name='profile-resources')
        self.thread.start()

    def _sample(self):
        rt = self.runtime
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while not self.stop.is_set():
            try:
                result = subprocess.run(['ps','-axo','pid=,ppid=,%cpu=,rss=,comm='],
                    capture_output=True,text=True,timeout=.5)
                rows = [line.split(maxsplit=4) for line in result.stdout.splitlines()]
                included = {os.getpid(),rt.host.expected_process_id}
                included.update(int(r[0]) for r in rows if len(r)==5 and '/ollama' in r[4])
                for _ in range(4):
                    included.update(int(r[0]) for r in rows if int(r[1]) in included)
                allocation = None
                try:
                    with opener.open('http://127.0.0.1:11434/api/ps',timeout=.2) as response:
                        models = json.loads(response.read(131072)).get('models',[])
                    allocation = [{k:m.get(k) for k in ('name','size','size_vram')}
                        for m in models if m.get('name') == rt.profile.backend_id]
                except Exception:
                    pass
                rt.event('resources',{'sample_monotonic':time.monotonic(),'processes':[
                    {'pid':int(r[0]),'cpu_percent':float(r[2]),'rss_kib':int(r[3])}
                    for r in rows if int(r[0]) in included], 'model_allocation':allocation,
                    'memory_policy':'RSS is process resident memory; size_vram is provider allocation, not measured GPU utilization'})
            except Exception:
                rt.event('resources_unavailable',{})
            self.stop.wait(1)

    def close(self):
        self.stop.set()
        self.thread.join(1)
        return not self.thread.is_alive()
