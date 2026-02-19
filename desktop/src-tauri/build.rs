use std::path::PathBuf;

fn main() {
    // Tauri requires sidecar binaries to exist at build time (even for `cargo check`).
    // Create a placeholder if the real binary hasn't been built yet.
    let target = std::env::var("TAURI_ENV_TARGET_TRIPLE")
        .unwrap_or_else(|_| "aarch64-apple-darwin".to_string());
    let sidecar = PathBuf::from(format!("binaries/brainshape-server-{target}"));
    if !sidecar.exists() {
        if let Some(parent) = sidecar.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        std::fs::write(&sidecar, b"").ok();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&sidecar, std::fs::Permissions::from_mode(0o755)).ok();
        }
    }

    tauri_build::build()
}
