// Empêche une console Windows de s'ouvrir en build release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const HANDSHAKE_PREFIX: &str = "CRM_SERVER_READY ";

/// Conserve le process du sidecar pour l'arrêter à la fermeture de l'app.
struct SidecarChild(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarChild(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();

            // Démarre le sidecar Python sur un port éphémère ; on lit son stdout
            // pour récupérer le handshake (port effectif + jeton de session).
            // `CRM_PARENT_PID` = notre PID : le sidecar surveille ce process et se
            // termine si l'app meurt (même brutalement), évitant les sidecars
            // orphelins qui se disputent le `cabinet.db` (cf. crm/server.py).
            let sidecar = handle
                .shell()
                .sidecar("crm-server")
                .expect("binaire sidecar « crm-server » introuvable (externalBin)")
                .args(["--port", "0"])
                .env("CRM_PARENT_PID", std::process::id().to_string());
            let (mut rx, child) = sidecar.spawn().expect("échec du démarrage du sidecar");

            // Mémorise l'enfant pour pouvoir le tuer à la sortie.
            app.state::<SidecarChild>().0.lock().unwrap().replace(child);

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(bytes) = event {
                        let line = String::from_utf8_lossy(&bytes);
                        if let Some(json) = line.trim().strip_prefix(HANDSHAKE_PREFIX) {
                            // Injecte { host, port, token } AVANT le chargement de la
                            // page : `window.__CRM_BACKEND__` est lu par src/lib/bridge.ts.
                            let init = format!("window.__CRM_BACKEND__ = {};", json.trim());
                            WebviewWindowBuilder::new(
                                &handle,
                                "main",
                                WebviewUrl::App("index.html".into()),
                            )
                            .title("Cabinet CRM")
                            .inner_size(1280.0, 840.0)
                            .min_inner_size(960.0, 640.0)
                            .initialization_script(&init)
                            .build()
                            .expect("échec de création de la fenêtre");
                            break;
                        }
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("erreur au démarrage de l'application Tauri")
        .run(|app_handle, event| {
            // Arrêt propre du sidecar quand l'application se ferme.
            if let RunEvent::Exit = event {
                if let Some(child) = app_handle.state::<SidecarChild>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
