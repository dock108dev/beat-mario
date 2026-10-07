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

        def windowShouldClose_(self, window):
            # The native close button has the same verified cleanup as Quit.
            AppKit.NSApplication.sharedApplication().terminate_(None)
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
    window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        Foundation.NSMakeRect(0, 0, 460, 190),
        AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
        | AppKit.NSWindowStyleMaskMiniaturizable,
        AppKit.NSBackingStoreBuffered, False)
    window.setTitle_('Game Companion')
    window.setDelegate_(delegate)
    window.setReleasedWhenClosed_(False)
    label = AppKit.NSTextField.labelWithString_(
        'Game Companion is running.\nOpen companion to discuss and review a game activity.\nQuit releases control and closes companion-owned test games.\nSaved configuration and results remain available when you reopen.')
    label.setFrame_(Foundation.NSMakeRect(24, 65, 412, 100))
    window.contentView().addSubview_(label)
    for title, x, width, action in (
        ('Open companion', 24, 180, 'openCompanion:'),
        ('Quit', 324, 112, 'terminate:')):
        button = AppKit.NSButton.alloc().initWithFrame_(Foundation.NSMakeRect(x, 20, width, 32))
        button.setTitle_(title)
        button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        button.setTarget_(delegate if action == 'openCompanion:' else app)
        button.setAction_(action)
        window.contentView().addSubview_(button)
    window.center()
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    menu = AppKit.NSMenu.alloc().init()
    item = AppKit.NSMenuItem.alloc().init()
    submenu = AppKit.NSMenu.alloc().initWithTitle_('Game Companion')
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
