# Release Process

## How to create a release

Push a version tag. CI handles everything else.

```bash
git tag v0.1.0
git push origin v0.1.0
```

## What happens automatically

1. GitHub Actions workflow (`.github/workflows/build.yml`) triggers on `v*` tags
2. Four parallel build jobs run:
   - macOS ARM64 (`macos-latest`) → `.dmg`
   - macOS Intel (`macos-13`) → `.dmg`
   - Windows (`windows-latest`) → `.msi`
   - Linux (`ubuntu-latest`) → `.AppImage` + `.deb`
3. Each job: PyInstaller builds the Python sidecar → copies to Tauri binaries → Tauri builds the app
4. A GitHub Release is auto-created with all artifacts attached (`softprops/action-gh-release`)
5. Release notes are auto-generated from commits since the last tag

## Where to find builds

- **In progress**: https://github.com/daniel-mallett/brainshape/actions
- **Completed releases**: https://github.com/daniel-mallett/brainshape/releases

## Local build (without CI)

```bash
./scripts/build-macos.sh          # Apple Silicon
./scripts/build-macos.sh x86_64   # Intel
```

Output: `desktop/src-tauri/target/release/bundle/dmg/`

## Not yet set up

- **macOS code signing & notarization**: Required for distributing to users outside the Mac App Store. Needs an Apple Developer ID certificate and environment variables set in GitHub Secrets (`APPLE_SIGNING_IDENTITY`, `APPLE_CERTIFICATE`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`). Without this, users get a Gatekeeper warning and must right-click → Open.
