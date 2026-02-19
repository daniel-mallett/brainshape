use std::net::TcpListener;
use std::sync::Mutex;

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

/// State shared between the Tauri setup and commands.
struct BackendState {
    port: u16,
}

/// Returns the port the Python backend is listening on.
#[tauri::command]
fn get_backend_port(state: tauri::State<'_, Mutex<BackendState>>) -> u16 {
    state.lock().unwrap().port
}

/// Bind to port 0 and let the OS assign a free port.
fn find_free_port() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").expect("Failed to bind to ephemeral port");
    listener.local_addr().unwrap().port()
}

/// Poll the backend health endpoint until it responds or we time out.
fn wait_for_health(port: u16, timeout_secs: u64) -> bool {
    let url = format!("http://127.0.0.1:{}/health", port);
    let start = std::time::Instant::now();
    let timeout = std::time::Duration::from_secs(timeout_secs);

    while start.elapsed() < timeout {
        if let Ok(resp) = reqwest::blocking::get(&url) {
            if resp.status().is_success() {
                return true;
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(200));
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // In debug builds, the developer runs the Python server manually.
            // Use the default dev port and skip sidecar spawn.
            if cfg!(debug_assertions) {
                app.manage(Mutex::new(BackendState { port: 8765 }));
                return Ok(());
            }

            let port = find_free_port();

            // Spawn the PyInstaller sidecar with the assigned port.
            let sidecar = app
                .shell()
                .sidecar("brainshape-server")
                .expect("Failed to find brainshape-server sidecar binary")
                .args(["--port", &port.to_string()]);

            let (mut rx, child) = sidecar.spawn().expect("Failed to spawn backend sidecar");

            // Forward sidecar output to the app's stdout/stderr for debugging.
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("[backend] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[backend] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(status) => {
                            eprintln!("[backend] process exited: {:?}", status);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            // Keep a handle so we can kill the child on shutdown.
            // Store it in a Box to move it into the event handler later.
            let child = Mutex::new(Some(child));
            app.manage(child);

            app.manage(Mutex::new(BackendState { port }));

            // Block until the backend is ready (or timeout after 60s).
            if !wait_for_health(port, 60) {
                return Err("Backend server failed to start within 60 seconds".into());
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill the sidecar when the last window closes.
                if let Some(child_state) =
                    window.try_state::<Mutex<Option<tauri_plugin_shell::process::CommandChild>>>()
                {
                    if let Ok(mut guard) = child_state.lock() {
                        if let Some(child) = guard.take() {
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
