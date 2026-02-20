use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::io::{BufRead, BufReader};

use tauri::Manager;

/// State shared between the Tauri setup and commands.
struct BackendState {
    port: u16,
}

/// Returns the port the Python backend is listening on.
#[tauri::command]
fn get_backend_port(state: tauri::State<'_, Mutex<BackendState>>) -> u16 {
    state.lock().unwrap().port
}

/// Default port for the Brainshape backend server.
/// Fixed so external MCP clients can reliably connect.
const DEFAULT_PORT: u16 = 52836;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // In debug builds, the developer runs the Python server manually.
            // Use the default dev port and skip sidecar spawn.
            if cfg!(debug_assertions) {
                app.manage(Mutex::new(BackendState { port: DEFAULT_PORT }));
                return Ok(());
            }

            let port = DEFAULT_PORT;

            // Find the sidecar in the bundled resources directory.
            let resource_dir = app
                .path()
                .resource_dir()
                .expect("Failed to resolve resource directory");
            let sidecar_exe = resource_dir
                .join("resources")
                .join("brainshape-server")
                .join("brainshape-server");

            if !sidecar_exe.exists() {
                eprintln!(
                    "[backend] Sidecar not found at: {}",
                    sidecar_exe.display()
                );
                app.manage(Mutex::new(BackendState { port }));
                return Ok(());
            }

            // Spawn the sidecar with stdout/stderr piped for forwarding.
            let mut child = Command::new(&sidecar_exe)
                .args(["--port", &port.to_string()])
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .expect("Failed to spawn backend sidecar");

            // Forward stdout in a background thread.
            if let Some(stdout) = child.stdout.take() {
                std::thread::spawn(move || {
                    let reader = BufReader::new(stdout);
                    for line in reader.lines() {
                        if let Ok(line) = line {
                            println!("[backend] {}", line);
                        }
                    }
                });
            }

            // Forward stderr in a background thread.
            if let Some(stderr) = child.stderr.take() {
                std::thread::spawn(move || {
                    let reader = BufReader::new(stderr);
                    for line in reader.lines() {
                        if let Ok(line) = line {
                            eprintln!("[backend] {}", line);
                        }
                    }
                });
            }

            // Keep a handle so we can kill the child on shutdown.
            app.manage(Mutex::new(Some(child)));
            app.manage(Mutex::new(BackendState { port }));

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill the sidecar when the last window closes.
                if let Some(child_state) = window.try_state::<Mutex<Option<Child>>>() {
                    if let Ok(mut guard) = child_state.lock() {
                        if let Some(ref mut child) = *guard {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
