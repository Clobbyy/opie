// OpieApp — the native macOS shell for the Opie control panel.
//
// A tiny AppKit + WebKit app that hosts the existing localhost control panel
// (opie/panel.py, http://127.0.0.1:8766) in a real window, plus a menu-bar item
// for Start/Stop/Restart. ALL relay logic stays in Python — this shell only
// renders the panel UI and calls its existing /api/* routes.
//
// Built locally at install time by opie/service.py with:
//   swiftc -O -o Opie main.swift -framework Cocoa -framework WebKit
// (No third-party dependencies; no code signing — a locally compiled binary
// delivered via git clone is never quarantined, so Gatekeeper stays quiet.)
//
// NOTE: compiled as `main.swift` so top-level code is permitted.

import Cocoa
import WebKit

let kPanelPort = 8766
let kPanelBase = "http://127.0.0.1:\(kPanelPort)"
let kPanelURL = URL(string: kPanelBase + "/")!

// Where the one-line installer records the source tree (config.set_install_root).
func installRoot() -> String? {
    let p = (NSHomeDirectory() as NSString)
        .appendingPathComponent("Library/Application Support/Opie/install_root")
    guard let s = try? String(contentsOfFile: p, encoding: .utf8) else { return nil }
    let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmed.isEmpty ? nil : trimmed
}

func findPython() -> String? {
    let candidates = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
    for c in candidates where FileManager.default.isExecutableFile(atPath: c) { return c }
    return nil
}

// Is the panel server answering yet?
func panelReachable(timeout: TimeInterval = 0.7) -> Bool {
    let sem = DispatchSemaphore(value: 0)
    var ok = false
    var req = URLRequest(url: URL(string: kPanelBase + "/api/state")!)
    req.timeoutInterval = timeout
    let task = URLSession.shared.dataTask(with: req) { _, resp, _ in
        if resp != nil { ok = true }
        sem.signal()
    }
    task.resume()
    _ = sem.wait(timeout: .now() + timeout + 0.3)
    return ok
}

// Launch the panel server (detached) if it isn't already up.
func spawnPanel() {
    guard let py = findPython() else { return }
    let p = Process()
    p.executableURL = URL(fileURLWithPath: py)
    p.arguments = ["-m", "opie.panel", "--no-browser"]
    var env = ProcessInfo.processInfo.environment
    if let root = installRoot() {
        let existing = env["PYTHONPATH"].map { ":" + $0 } ?? ""
        env["PYTHONPATH"] = root + existing
        p.currentDirectoryURL = URL(fileURLWithPath: root)
    }
    p.environment = env
    p.standardOutput = FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice
    try? p.run()  // fire and forget — panel.py keeps only the freshest instance
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var statusItem: NSStatusItem!
    var pollTimer: Timer?

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMainMenu()
        buildWindow()
        buildMenuBar()
        bringUpPanel()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            self?.refreshStatus()
        }
        refreshStatus()
    }

    // ---- window + webview ----
    func buildWindow() {
        let cfg = WKWebViewConfiguration()
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 980, height: 760),
                            configuration: cfg)
        webView.navigationDelegate = self
        loadPlaceholder("Starting Opie…", "Bringing up the control panel.")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 980, height: 760),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Opie"
        window.setFrameAutosaveName("OpieMainWindow")
        window.contentView = webView
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func loadPlaceholder(_ title: String, _ subtitle: String) {
        let html = """
        <html><body style="font-family:-apple-system,system-ui;background:#1d1d1f;
        color:#f5f5f7;display:flex;height:100vh;margin:0;align-items:center;
        justify-content:center;text-align:center">
        <div><h2 style="font-weight:600">\(title)</h2>
        <p style="color:#86868b">\(subtitle)</p></div></body></html>
        """
        webView.loadHTMLString(html, baseURL: nil)
    }

    func bringUpPanel() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            if !panelReachable() { spawnPanel() }
            var up = false
            for _ in 0..<25 {            // ~10s
                if panelReachable() { up = true; break }
                Thread.sleep(forTimeInterval: 0.4)
            }
            DispatchQueue.main.async {
                guard let self = self else { return }
                if up {
                    self.webView.load(URLRequest(url: kPanelURL))
                } else {
                    self.loadPlaceholder("Couldn’t start the control panel",
                        "Open Terminal and run the Opie installer again, then reopen Opie.")
                }
            }
        }
    }

    // Send external links (docs, GitHub, etc.) to the default browser.
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = action.request.url, let host = url.host,
           host != "127.0.0.1" && host != "localhost" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    // ---- menu bar ----
    func buildMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        let menu = NSMenu()
        let open = menu.addItem(withTitle: "Open Opie Control",
                                action: #selector(openPanel), keyEquivalent: "")
        open.target = self
        menu.addItem(.separator())
        for (title, sel) in [("Start Relay", #selector(startRelay)),
                             ("Stop Relay", #selector(stopRelay)),
                             ("Restart Relay", #selector(restartRelay))] {
            let it = menu.addItem(withTitle: title, action: sel, keyEquivalent: "")
            it.target = self
        }
        menu.addItem(.separator())
        let quit = menu.addItem(withTitle: "Quit Opie",
                                action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quit.target = NSApp
        statusItem.menu = menu
        applyStatus(running: false)
    }

    func applyStatus(running: Bool) {
        guard let button = statusItem.button else { return }
        let symbol = running ? "mic.circle.fill" : "mic.circle"
        if #available(macOS 11.0, *),
           let img = NSImage(systemSymbolName: symbol, accessibilityDescription: "Opie") {
            img.isTemplate = true
            button.image = img
            button.title = ""
        } else {
            button.image = nil
            button.title = running ? "●" : "○"
        }
        button.toolTip = running ? "Opie — relay running" : "Opie — relay stopped"
    }

    func refreshStatus() {
        var req = URLRequest(url: URL(string: kPanelBase + "/api/state")!)
        req.timeoutInterval = 1.5
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            var running = false
            if let d = data,
               let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
               let s = j["status"] as? [String: Any],
               let r = s["running"] as? Bool {
                running = r
            }
            DispatchQueue.main.async { self?.applyStatus(running: running) }
        }.resume()
    }

    func control(_ action: String) {
        var req = URLRequest(url: URL(string: kPanelBase + "/api/control")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["action": action])
        req.timeoutInterval = 10
        URLSession.shared.dataTask(with: req) { [weak self] _, _, _ in
            DispatchQueue.main.async { self?.refreshStatus() }
        }.resume()
    }

    @objc func openPanel() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    @objc func startRelay() { control("start") }
    @objc func stopRelay() { control("stop") }
    @objc func restartRelay() { control("restart") }

    // Keep running in the menu bar after the window is closed; reopen on Dock click.
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ app: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { window.makeKeyAndOrderFront(nil) }
        return true
    }

    // Minimal main menu so ⌘Q/⌘W and copy/paste work inside the panel.
    func buildMainMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Hide Opie",
                        action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Opie",
                        action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let editItem = NSMenuItem()
        main.addItem(editItem)
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All",
                         action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = editMenu
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
