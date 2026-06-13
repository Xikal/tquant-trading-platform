mod commands;
mod paths;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::read_desktop_config,
            commands::write_desktop_config,
            commands::open_log_dir,
            commands::open_data_dir
        ])
        .run(tauri::generate_context!())
        .expect("failed to run TQuant Local");
}
