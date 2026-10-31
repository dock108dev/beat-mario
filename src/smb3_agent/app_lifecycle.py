"""Native Quit, signal and interrupted-startup status for the local app."""
from pathlib import Path
import json
import os
import threading


def record_lifecycle(state, failures=()):
    path = Path('app-lifecycle.json')
    value = {'state': state, 'pid': os.getpid(), 'authority_restored': False, 'cleanup_failures': list(failures)}
    if state == 'running' and path.is_file():
        try:
            previous = json.loads(path.read_text())
            value['interrupted_previous_start'] = previous.get('state') != 'closed'
            value['previous_cleanup_failures'] = previous.get('cleanup_failures', [])
        except (OSError, ValueError):
            value['interrupted_previous_start'] = True
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def run_native(server):
    """Keep the Cocoa event loop responsive to Finder/Dock/Cmd-Q termination."""
    import AppKit
    import Foundation
    import objc

    closed = False
    cleanup_failed = False
    def close():
        nonlocal closed, cleanup_failed
        if closed:
            return
        server.delivery_stopping = True
        server.shutdown()
        try:
            server.server_close()
        except Exception as exc:
            cleanup_failed = True
            record_lifecycle('cleanup_failed', (str(exc),))
            raise
        closed = True
        cleanup_failed = False
        record_lifecycle('closed')

    class CompanionDelegate(Foundation.NSObject):
        def applicationShouldTerminate_(self, app):
            try:
                close()
            except Exception as exc:
                alert = AppKit.NSAlert.alloc().init()
                alert.setMessageText_('Game Companion cleanup needs attention')
                alert.setInformativeText_(str(exc) + '\nInspect cleanup-failures.json in local app data.')
                alert.runModal()
                return AppKit.NSTerminateCancel
            return AppKit.NSTerminateNow

        def openCompanion_(self, sender):
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{server.server_port}/')

        def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
            self.openCompanion_(None)
            return False

        def poll_(self, timer):
            if not worker.is_alive() and not cleanup_failed:
                AppKit.NSApplication.sharedApplication().terminate_(None)

    import signal
    previous = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, lambda signum, frame: threading.Thread(target=server.shutdown, daemon=True).start())
    app = AppKit.NSApplication.sharedApplication()
    delegate = CompanionDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    # The browser is the play window. Keep only the Dock/menu lifecycle so
    # there is no second, empty launcher window competing with it.
    menu = AppKit.NSMenu.alloc().init()
    item = AppKit.NSMenuItem.alloc().init()
    submenu = AppKit.NSMenu.alloc().initWithTitle_('Game Companion')
    open_item = submenu.addItemWithTitle_action_keyEquivalent_('Open Game Companion', 'openCompanion:', 'o')
    open_item.setTarget_(delegate)
    submenu.addItemWithTitle_action_keyEquivalent_('Quit Game Companion', 'terminate:', 'q')
    item.setSubmenu_(submenu)
    menu.addItem_(item)
    app.setMainMenu_(menu)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(.25, delegate, objc.selector(delegate.poll_, signature=b'v@:@'), None, True)
    try:
        app.run()
    finally:
        timer.invalidate()
        close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
