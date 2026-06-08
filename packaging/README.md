# Packaging Opie for macOS

This folder turns the repo into a native, double-clickable macOS installer so a
non-technical user can install Opie without Terminal, Git, or `pip`.

| Artifact | How the user installs | Best for |
|---|---|---|
| **`Opie-<ver>.pkg`** | Double-click → guided installer → app lands in **Applications**. | Most people. |
| **`Opie-<ver>.dmg`** | Double-click → drag **Opie** onto **Applications**. | Familiar Mac flow. |

Both wrap the same **`Opie.app`**, a thin launcher (`Contents/MacOS/Opie`) that
runs the Python package bundled in `Contents/Resources/opie` using a Tk-8.6+
Python found on the system. The first launch creates the user's config (with a
fresh token) and records where the code lives, so there's nothing to configure
by hand and no root-owned files.

## Build locally (on a Mac)

```bash
packaging/build_all.sh        # both, into ./dist
# or individually:
packaging/build_pkg.sh
packaging/build_dmg.sh
packaging/build_app.sh ./dist # just the .app (runs on any OS — layout testing)
```

The version is read from `opie/__init__.py` (`__version__`) — bump it there.

## Build in CI (no Mac needed)

`.github/workflows/release.yml` builds both installers on `macos-latest`:

- **Every run** uploads them as **workflow artifacts** (Actions → run → Artifacts)
  — trigger manually from the Actions tab ("Run workflow").
- **Pushing a tag** like `v0.2.0` also attaches them to a **GitHub Release**, so
  buyers just grab `Opie-0.2.0.pkg` from the Releases page.

```bash
git tag v0.2.0 && git push origin v0.2.0
```

## Updates

- The **`.pkg`/`.dmg`** installs a self-contained copy; update it by installing a
  newer one (the control panel's "Check for updates" opens the Releases page).
- A **Git clone** + `install.command` keeps itself current automatically
  (`git pull` on start) — see the top-level README. Pick whichever fits the user.

## Signing & notarization (optional, removes the Gatekeeper prompt)

The installers are **unsigned**, so the first open needs right-click → **Open**
(or System Settings → Privacy & Security → **Open Anyway**). To ship a one-click
experience you need an Apple Developer ID:

```bash
# sign the app, then the installer, then notarize + staple
codesign --deep --force --options runtime --sign "Developer ID Application: …" dist/Opie.app
productsign --sign "Developer ID Installer: …" dist/Opie-<ver>.pkg dist/Opie-<ver>-signed.pkg
xcrun notarytool submit dist/Opie-<ver>-signed.pkg --keychain-profile "AC_PASSWORD" --wait
xcrun stapler staple dist/Opie-<ver>-signed.pkg
```

Drop an `app/AppIcon.icns` here to brand the app icon (optional).
