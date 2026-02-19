# Release Process

## How to create a release

Push a version tag. CI handles everything else.

```bash
git tag v0.1.0
git push origin v0.1.0
```

## What happens automatically

1. GitHub Actions workflow (`.github/workflows/build.yml`) triggers on `v*` tags
2. macOS ARM64 build job runs on `macos-latest`:
   - PyInstaller builds the Python sidecar
   - Copies sidecar to Tauri binaries directory
   - Tauri builds the app and produces a `.dmg`
3. A GitHub Release is auto-created with the `.dmg` attached (`softprops/action-gh-release`)
4. Release notes are auto-generated from commits since the last tag

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

- **macOS code signing & notarization**: Required for distributing to users outside the Mac App Store. Needs an Apple Developer ID certificate and environment variables set in GitHub Secrets (`APPLE_SIGNING_IDENTITY`, `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `KEYCHAIN_PASSWORD`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`). Without this, users get a Gatekeeper warning and must run `xattr -cr /Applications/Brainshape.app` before first launch.
- **Other platforms**: Windows and Linux builds can be added back to the CI matrix when needed (see git history for the matrix config).
