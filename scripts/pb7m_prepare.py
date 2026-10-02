"""Explicitly reviewed menu-only preparation for an exact fresh Java process.

This script is engineering preparation, never execution/qualification evidence.
No saves, credentials, JVM arguments, or game-state files are read.
"""
import argparse
from pathlib import Path
import hashlib
import json
import subprocess
import time
from uuid import uuid4

from smb3_agent.screen_host import MacSelectedWindowHost, recognize_text
from smb3_agent.ordinary_input import MacProfileInput
from smb3_agent.host_contracts import InputCommand, InputKind, HostError
from smb3_agent.coordinate_contracts import WindowCoordinates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--window', required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--click', nargs=2, type=float)
    parser.add_argument('--expect')
    parser.add_argument('--pointer',nargs=2,type=float)
    parser.add_argument('--name')
    parser.add_argument('--key', choices=['escape','f3'])
    args=parser.parse_args()
    # The original incoming Singleplayer process is explicitly excluded.
    if args.pid == 74438:
        raise HostError('Incoming personal process is excluded')
    args.root.mkdir(parents=True, exist_ok=True)
    started=subprocess.check_output(['ps','-p',str(args.pid),'-o','lstart='],text=True).strip()
    host=MacSelectedWindowHost(args.pid,started,args.window,background_observation=True)
    # Preparation may raise this exact fresh process while another app overlaps.
    # No input is sent until the ordinary full foreground/occlusion guard passes.
    import AppKit
    import Quartz as q
    rows=q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionAll,q.kCGNullWindowID) or ()
    matches=[r for r in rows if r.get(q.kCGWindowOwnerPID)==args.pid
             and str(r.get(q.kCGWindowNumber))==args.window and r.get(q.kCGWindowLayer)==0]
    if len(matches)!=1:
        raise HostError('Preparation process/window unavailable')
    import ApplicationServices as ax
    application=ax.AXUIElementCreateApplication(args.pid)
    ax.AXUIElementSetAttributeValue(application,ax.kAXFrontmostAttribute,True)
    error,windows=ax.AXUIElementCopyAttributeValue(application,ax.kAXWindowsAttribute,None)
    if error:
        raise HostError('Exact preparation accessibility window unavailable')
    for w in windows or ():
        error,title=ax.AXUIElementCopyAttributeValue(w,ax.kAXTitleAttribute,None)
        if title==matches[0].get(q.kCGWindowName):
            ax.AXUIElementPerformAction(w,ax.kAXRaiseAction)
    AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(args.pid).activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    from smb3_agent.native_host import foreground_process_id
    until=time.monotonic()+1
    while foreground_process_id()!=args.pid and time.monotonic()<until:
        time.sleep(.01)
    window=host.detect_window()
    path=args.root/(uuid4().hex+'.png')
    at=time.monotonic()
    host.capture(window,path)
    text=recognize_text(path) if args.click or args.name or args.pointer else ()
    readable='\n'.join(t.text for t in text)
    if args.click or args.name or args.pointer:
        if not args.expect or args.expect.casefold() not in readable.casefold():
            raise HostError('Reviewed menu label is unavailable: '+readable)
        if ('Facing:' in readable or 'XYZ:' in readable) and not ('Game Menu' in readable and 'Back to Game' in readable):
            raise HostError('World interaction prohibited during menu preparation')
    def authority():
        if time.monotonic()-at > 3:
            raise HostError('Preparation observation expired')
    def isolation(current):
        if (current.process_id,current.process_started_at,current.window_id,current.bounds)!=(window.process_id,window.process_started_at,window.window_id,window.bounds):
            raise HostError('Exact preparation window changed')
    driver=MacProfileInput(window_provider=host.detect_window,authority_guard=authority,isolation_guard=isolation)
    driver.arm()
    if args.pointer:
        target=WindowCoordinates(window.bounds,window.bounds[2:]).native_point(*args.pointer)
        driver.send(InputCommand(InputKind.MOUSE,'move','move',0,target=target,purpose='menu_pointer'))
    if args.click:
        target=WindowCoordinates(window.bounds,window.bounds[2:]).native_point(*args.click)
        driver.send(InputCommand(InputKind.MOUSE,'move','move',0,target=target,purpose='menu_pointer'))
        time.sleep(.08)
        driver.send(InputCommand(InputKind.MOUSE,'left_button','click',40,target=target,purpose='reviewed_menu_only'))
    if args.name:
        if not args.name.startswith('PB7M Camera ') or len(args.name)>80 or '\n' in args.name:
            raise HostError('Only the dedicated practice-world name may be typed')
        q=driver.q
        authority(); isolation(host.detect_window())
        # Replace only the reviewed world-name field, with a finite chord.
        q.CGEventPost(q.kCGHIDEventTap,q.CGEventCreateKeyboardEvent(None,55,True))
        for pressed in (True,False):
            event=q.CGEventCreateKeyboardEvent(None,0,pressed)
            q.CGEventSetFlags(event,q.kCGEventFlagMaskCommand)
            q.CGEventPost(q.kCGHIDEventTap,event)
        q.CGEventPost(q.kCGHIDEventTap,q.CGEventCreateKeyboardEvent(None,55,False))
        # Menu field only; UTF-16 text, never gameplay commands.
        codes={c:k for c,k in zip('abcdefghijklmnopqrstuvwxyz0123456789 ',
            [0,11,8,2,14,3,5,4,34,38,40,37,46,45,31,35,12,15,1,17,32,9,13,7,16,6,29,18,19,20,21,23,22,26,28,25,49])}
        time.sleep(.05)
        for char in args.name:
            code=codes[char.lower()]
            for pressed in (True,False):
                event=q.CGEventCreateKeyboardEvent(None,code,pressed)
                q.CGEventSetFlags(event,q.kCGEventFlagMaskShift if char.isupper() else 0)
                q.CGEventPost(q.kCGHIDEventTap,event)
            time.sleep(.01)
    if args.key:
        q=driver.q; code=53 if args.key=='escape' else 99
        isolation(host.detect_window()); authority()
        q.CGEventPost(q.kCGHIDEventTap,q.CGEventCreateKeyboardEvent(None,code,True))
        q.CGEventPost(q.kCGHIDEventTap,q.CGEventCreateKeyboardEvent(None,code,False))
    driver.neutralize()
    receipt=driver.release_receipt()
    after=args.root/(uuid4().hex+'-after.png')
    host.capture(host.detect_window(),after)
    record={'class':'world_preparation_only','pid':args.pid,'started':started,'window':args.window,
            'before':str(path),'before_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'after':str(after),'expected_menu_label':args.expect,'action':{'click':args.click,'pointer':args.pointer,'name':args.name,'key':args.key},'release':receipt}
    (args.root/(path.stem+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))


if __name__=='__main__':
    main()
