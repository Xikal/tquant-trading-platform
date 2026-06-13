use std::path::{Path, PathBuf};

pub fn project_root() -> PathBuf {
    if let Ok(value) = std::env::var("TQUANT_PROJECT_ROOT") {
        let path = PathBuf::from(value);
        if !path.as_os_str().is_empty() {
            return path;
        }
    }
    if let Ok(executable) = std::env::current_exe() {
        let root = infer_project_root(&executable);
        if root != executable {
            return root;
        }
    }
    let current = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    infer_project_root(&current)
}

pub fn infer_project_root(start: &Path) -> PathBuf {
    let mut current = start.to_path_buf();
    for _ in 0..16 {
        if current.file_name().and_then(|name| name.to_str()) == Some("src-tauri") {
            if let Some(root) = current.parent().and_then(|parent| parent.parent()) {
                return root.to_path_buf();
            }
        }
        if current.file_name().and_then(|name| name.to_str()) == Some("frontend-next") {
            if let Some(root) = current.parent() {
                return root.to_path_buf();
            }
        }
        if current.join("frontend-next").is_dir() && current.join("backend").is_dir() {
            return current;
        }
        if let Some(parent) = current.parent() {
            current = parent.to_path_buf();
        } else {
            break;
        }
    }
    start.to_path_buf()
}

pub fn config_path() -> PathBuf {
    project_root().join("frontend-next").join(".tquant-desktop.json")
}

pub fn log_dir() -> PathBuf {
    project_root().join("logs")
}

pub fn data_dir() -> PathBuf {
    project_root().join("backend").join("data")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn infers_project_root_from_src_tauri_path() {
        let root = PathBuf::from("/tmp/gupiao");
        let start = root.join("frontend-next").join("src-tauri");

        assert_eq!(infer_project_root(&start), root);
    }

    #[test]
    fn infers_project_root_from_bundled_app_executable_path() {
        let root = PathBuf::from("/tmp/gupiao");
        let executable = root
            .join("frontend-next")
            .join("src-tauri")
            .join("target")
            .join("release")
            .join("bundle")
            .join("macos")
            .join("TQuant Local.app")
            .join("Contents")
            .join("MacOS")
            .join("tquant-local");

        assert_eq!(infer_project_root(&executable), root);
    }
}
