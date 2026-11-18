use std::env;
use std::fs;
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendState {
    port: u16,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn get_backend_url(state: tauri::State<'_, BackendState>) -> String {
    format!("http://127.0.0.1:{}/api/v1", state.port)
}

#[tauri::command]
fn get_platform() -> &'static str {
    std::env::consts::OS
}

fn is_port_listening(port: u16) -> bool {
    TcpStream::connect_timeout(
        &SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(120),
    )
    .is_ok()
}

fn pick_available_port(preferred: u16) -> u16 {
    if let Ok(listener) = TcpListener::bind(("127.0.0.1", preferred)) {
        if let Ok(addr) = listener.local_addr() {
            return addr.port();
        }
        return preferred;
    }
    if let Ok(listener) = TcpListener::bind(("127.0.0.1", 0)) {
        if let Ok(addr) = listener.local_addr() {
            return addr.port();
        }
    }
    preferred
}

fn locate_packaged_backend(app: &tauri::App) -> Option<(PathBuf, PathBuf)> {
    let bin_name = if cfg!(target_os = "windows") {
        "uniphoto-backend.exe"
    } else {
        "uniphoto-backend"
    };

    let mut resource_roots: Vec<PathBuf> = Vec::new();
    if let Ok(res_dir) = app.path().resource_dir() {
        resource_roots.push(res_dir);
    }
    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let exe_dir_buf = exe_dir.to_path_buf();
            if !resource_roots.contains(&exe_dir_buf) {
                resource_roots.push(exe_dir_buf);
            }
            if let Some(contents_dir) = exe_dir.parent() {
                let macos_resources = contents_dir.join("Resources");
                if !resource_roots.contains(&macos_resources) {
                    resource_roots.push(macos_resources);
                }
            }
        }
    }

    for root in resource_roots {
        let direct_bin = root.join("backend").join(bin_name);
        if direct_bin.is_file() {
            return Some((direct_bin, root));
        }
        let nested_bin = root
            .join("backend")
            .join("uniphoto-backend")
            .join(bin_name);
        if nested_bin.is_file() {
            return Some((nested_bin, root));
        }
    }

    None
}

fn venv_python_path(root: &Path) -> PathBuf {
    if cfg!(target_os = "windows") {
        root.join(".venv").join("Scripts").join("python.exe")
    } else {
        root.join(".venv").join("bin").join("python")
    }
}

fn clean_canonical_path(path: &Path) -> PathBuf {
    if let Ok(canon) = fs::canonicalize(path) {
        #[cfg(target_os = "windows")]
        {
            let raw = canon.to_string_lossy();
            if let Some(unc) = raw.strip_prefix(r"\\?\UNC\") {
                return PathBuf::from(format!(r"\\{}", unc));
            }
            if let Some(stripped) = raw.strip_prefix(r"\\?\") {
                return PathBuf::from(stripped);
            }
        }
        return canon;
    }
    path.to_path_buf()
}

fn locate_dev_repo_backend() -> Option<(PathBuf, PathBuf, PathBuf)> {
    let mut candidate_roots: Vec<PathBuf> = vec![
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."),
    ];
    if let Ok(cwd) = env::current_dir() {
        candidate_roots.push(cwd.clone());
        candidate_roots.push(cwd.join(".."));
        candidate_roots.push(cwd.join("../.."));
    }

    for root in candidate_roots {
        let python_bin = venv_python_path(&root);
        let run_script = root.join("run.py");
        if python_bin.is_file() && run_script.is_file() {
            let canonical_root = clean_canonical_path(&root);
            let canonical_py = venv_python_path(&canonical_root);
            let canonical_run = canonical_root.join("run.py");
            if canonical_py.is_file() && canonical_run.is_file() {
                return Some((canonical_root, canonical_py, canonical_run));
            }
            return Some((canonical_root, python_bin, run_script));
        }
    }

    None
}

fn fallback_app_data_dir() -> PathBuf {
    if cfg!(target_os = "windows") {
        if let Some(local_app_data) = env::var_os("LOCALAPPDATA") {
            return PathBuf::from(local_app_data).join("UniPhoto");
        }
        if let Some(user_profile) = env::var_os("USERPROFILE") {
            return PathBuf::from(user_profile)
                .join("AppData")
                .join("Local")
                .join("UniPhoto");
        }
        return env::temp_dir().join("UniPhoto");
    }

    let home = env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(env::temp_dir);
    home.join("Library")
        .join("Application Support")
        .join("com.hung.uniphoto")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_backend_url, get_platform])
        .setup(|app| {
            if let Some(icon) = app.default_window_icon().cloned() {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.set_icon(icon);
                }
            }

            #[cfg(target_os = "macos")]
            if let Some(window) = app.get_webview_window("main") {
                use tauri::window::{Effect, EffectState, EffectsBuilder};
                let _ = window.set_effects(
                    EffectsBuilder::new()
                        .effect(Effect::Sidebar)
                        .state(EffectState::Active)
                        .build(),
                );
            }

            #[cfg(target_os = "windows")]
            if let Some(window) = app.get_webview_window("main") {
                use tauri::window::{Effect, EffectsBuilder};
                let _ = window.set_effects(
                    EffectsBuilder::new()
                        .effect(Effect::Mica)
                        .build(),
                );
            }

            if let Some((backend_bin, resources_root)) = locate_packaged_backend(app) {
                let preferred_port = env::var("UNIPHOTO_BACKEND_PORT")
                    .ok()
                    .and_then(|s| s.parse::<u16>().ok())
                    .unwrap_or(8000);
                let port = pick_available_port(preferred_port);

                let data_dir = app
                    .path()
                    .app_data_dir()
                    .unwrap_or_else(|_| fallback_app_data_dir());
                let _ = fs::create_dir_all(&data_dir);
                let mpl_dir = env::temp_dir().join("uniphoto-mpl");
                let _ = fs::create_dir_all(&mpl_dir);

                let direct_models = resources_root.join("models");
                let nested_models = direct_models.join("bundled-models");
                let models_dir = if !direct_models.join("face_landmarker.task").is_file()
                    && !direct_models.join("mobilenet_v2.onnx").is_file()
                    && !direct_models.join("mobilenet_v2.pth").is_file()
                    && nested_models.is_dir()
                {
                    nested_models
                } else {
                    direct_models
                };

                let mut cmd = Command::new(&backend_bin);
                cmd.current_dir(&data_dir)
                    .env("HOST", "127.0.0.1")
                    .env("PORT", port.to_string())
                    .env("DEBUG", "False")
                    .env("UNIPHOTO_PACKAGED", "1")
                    .env("UNIPHOTO_DATA_DIR", &data_dir)
                    .env("UNIPHOTO_MODELS_DIR", &models_dir)
                    .env("UNIPHOTO_PARENT_PID", std::process::id().to_string())
                    .env("MPLCONFIGDIR", &mpl_dir)
                    .stdin(Stdio::null())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null());

                #[cfg(target_os = "windows")]
                {
                    use std::os::windows::process::CommandExt;
                    const CREATE_NO_WINDOW: u32 = 0x08000000;
                    cmd.creation_flags(CREATE_NO_WINDOW);
                }

                let spawned_child = cmd.spawn();

                app.manage(BackendState {
                    port,
                    child: Mutex::new(spawned_child.ok()),
                });
            } else {
                let env_port = env::var("UNIPHOTO_BACKEND_PORT")
                    .ok()
                    .and_then(|s| s.parse::<u16>().ok())
                    .unwrap_or(8000);

                if is_port_listening(env_port) {
                    app.manage(BackendState {
                        port: env_port,
                        child: Mutex::new(None),
                    });
                } else if let Some((repo_root, python_bin, run_script)) = locate_dev_repo_backend()
                {
                    let port = pick_available_port(env_port);
                    let mpl_dir = env::temp_dir().join("uniphoto-mpl");
                    let _ = fs::create_dir_all(&mpl_dir);

                    let mut cmd = Command::new(&python_bin);
                    cmd.arg(&run_script)
                        .current_dir(&repo_root)
                        .env("HOST", "127.0.0.1")
                        .env("PORT", port.to_string())
                        .env("DEBUG", "False")
                        .env("UNIPHOTO_PARENT_PID", std::process::id().to_string())
                        .env("MPLCONFIGDIR", &mpl_dir)
                        .stdin(Stdio::null())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null());

                    #[cfg(target_os = "windows")]
                    {
                        use std::os::windows::process::CommandExt;
                        const CREATE_NO_WINDOW: u32 = 0x08000000;
                        cmd.creation_flags(CREATE_NO_WINDOW);
                    }

                    let spawned_child = cmd.spawn();

                    app.manage(BackendState {
                        port,
                        child: Mutex::new(spawned_child.ok()),
                    });
                } else {
                    app.manage(BackendState {
                        port: env_port,
                        child: Mutex::new(None),
                    });
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    if let Ok(mut guard) = state.child.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        });
}
