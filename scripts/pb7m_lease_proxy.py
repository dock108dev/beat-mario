"""Bounded loopback network fault for ordinary camera-page heartbeat delivery.

Serve the unchanged ordinary panel through a local reverse proxy. A retained
file gate drops actual heartbeat HTTP requests for at most eight seconds while
GET evidence, direct controls and the native controller remain live. No service
state, camera policy, world state or frame content is injected.
"""
import argparse
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import parse_qs
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();a.root.mkdir(parents=True,exist_ok=True);gate=a.root/'lease-gate.json';log=a.root/'network-fault.jsonl'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_GET(self):self.forward()
 def do_POST(self):self.forward()
 def forward(self):
  body=self.rfile.read(int(self.headers.get('Content-Length','0')));action=parse_qs(body.decode('utf8')).get('action',[''])[0] if self.command=='POST' else ''
  state={}
  if gate.exists():
   try:state=json.loads(gate.read_text())
   except ValueError:pass
  if action=='heartbeat' and 0<=time.monotonic()-state.get('began_at',-999)<=8:
   with log.open('a') as f:f.write(json.dumps({'at':time.monotonic(),'wall_ns':time.time_ns(),'action':action,'fault':'heartbeat_HTTP_503','max_gate_seconds':8,'body_sha256':hashlib.sha256(body).hexdigest()})+'\n')
   self.send_response(503);self.send_header('Content-Type','application/json');data=b'{"error":"bounded heartbeat network fault"}';self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
   return
  headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','connection','content-length'}};headers['Host']='127.0.0.1:8809';headers['Content-Length']=str(len(body))
  if headers.get('Origin')=='http://127.0.0.1:8810':headers['Origin']='http://127.0.0.1:8809'
  connection=http.client.HTTPConnection('127.0.0.1',8809,timeout=5)
  try:
   connection.request(self.command,self.path,body,headers);response=connection.getresponse();data=response.read();self.send_response(response.status)
   for k,v in response.getheaders():
    if k.lower() not in {'connection','transfer-encoding','content-length','server','date'}:self.send_header(k,v)
   self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  finally:connection.close()
ThreadingHTTPServer(('127.0.0.1',8810),Handler).serve_forever()
