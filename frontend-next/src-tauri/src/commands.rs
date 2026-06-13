use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::process::Command;

use crate::paths;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DesktopConfig {
    pub api_base_url: String,
}

impl Default for DesktopConfig {
    fn default() -> Self {
        Self {
            api_base_url: String::new(),
        }
    }
}

#[tauri::command]
pub fn read_desktop_config() -> Result<DesktopConfig, String> {
    read_config_from_path(&paths::config_path()).map_err(safe_error)
}

#[tauri::command]
pub fn write_desktop_config(config: DesktopConfig) -> Result<DesktopConfig, String> {
    let normalized = normalize_api_base_url(&config.api_base_url)
        .ok_or_else(|| "API 地址仅支持 http 或 https".to_string())?;
    let next = DesktopConfig {
        api_base_url: normalized,
    };
    write_config_to_path(&paths::config_path(), &next).map_err(safe_error)?;
    Ok(next)
}

#[tauri::command]
pub fn open_log_dir() -> Result<(), String> {
    open_existing_path_or_fallback(&paths::log_dir(), &paths::project_root())
}

#[tauri::command]
pub fn open_data_dir() -> Result<(), String> {
    open_path(&paths::data_dir())
}

pub fn normalize_api_base_url(value: &str) -> Option<String> {
    let trimmed = value.trim().trim_end_matches('/').to_string();
    if trimmed.is_empty() {
        return Some(String::new());
    }
    if (trimmed.starts_with("http://") || trimmed.starts_with("https://")) && !trimmed.chars().any(char::is_whitespace) {
        return Some(trimmed);
    }
    None
}

fn read_config_from_path(path: &Path) -> Result<DesktopConfig, Box<dyn std::error::Error>> {
    if !path.exists() {
        return Ok(DesktopConfig::default());
    }
    let content = fs::read_to_string(path)?;
    let config: DesktopConfig = serde_json::from_str(&content)?;
    Ok(DesktopConfig {
        api_base_url: normalize_api_base_url(&config.api_base_url).unwrap_or_default(),
    })
}

fn write_config_to_path(path: &Path, config: &DesktopConfig) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, serde_json::to_vec_pretty(config)?)?;
    Ok(())
}

fn open_path(path: &Path) -> Result<(), String> {
    if !path.exists() {
        return Err(format!("目录不存在：{}", path.display()));
    }
    let mut command = platform_open_command(path);
    let status = command.status().map_err(|error| format!("目录打开失败：{}", error))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("目录打开失败：{}", path.display()))
    }
}

fn open_existing_path_or_fallback(path: &Path, fallback: &Path) -> Result<(), String> {
    open_path(&path_to_open(path, fallback)?)
}

fn path_to_open(path: &Path, fallback: &Path) -> Result<std::path::PathBuf, String> {
    if path.exists() {
        return Ok(path.to_path_buf());
    }
    if fallback.exists() {
        return Ok(fallback.to_path_buf());
    }
    Err(format!("目录不存在：{}", path.display()))
}

#[cfg(target_os = "macos")]
fn platform_open_command(path: &Path) -> Command {
    let mut command = Command::new("open");
    command.arg(path);
    command
}

#[cfg(target_os = "windows")]
fn platform_open_command(path: &Path) -> Command {
    let mut command = Command::new("cmd");
    command.args(["/C", "start", "", &path.display().to_string()]);
    command
}

#[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
fn platform_open_command(path: &Path) -> Command {
    let mut command = Command::new("xdg-open");
    command.arg(path);
    command
}

fn safe_error(error: Box<dyn std::error::Error>) -> String {
    error.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_http_api_base_url() {
        assert_eq!(
            normalize_api_base_url(" http://127.0.0.1:8000/// "),
            Some("http://127.0.0.1:8000".to_string())
        );
        assert_eq!(
            normalize_api_base_url("https://example.test/api/"),
            Some("https://example.test/api".to_string())
        );
    }

    #[test]
    fn rejects_non_http_api_base_url() {
        assert_eq!(normalize_api_base_url("file:///tmp/app"), None);
        assert_eq!(normalize_api_base_url("javascript:alert(1)"), None);
    }

    #[test]
    fn missing_log_dir_can_fallback_to_project_root_without_creating_directory() {
        let root = std::env::temp_dir().join(format!(
            "tquant-local-command-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time")
                .as_nanos()
        ));
        std::fs::create_dir_all(&root).expect("create temp root");
        let missing_logs = root.join("logs");

        assert_eq!(path_to_open(&missing_logs, &root).expect("fallback path"), root);
        assert!(!missing_logs.exists());

        std::fs::remove_dir_all(&root).expect("remove temp root");
    }
}
