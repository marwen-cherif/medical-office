# Project Rules

## Git & Version Control (Public Repository Security)

- **Zero Sensitive Data Exposure**: Because this repository is **public**, absolutely NO sensitive data (private keys, certificates, credentials, personal data, local settings) must ever be committed.
- **Proactive Gitignore Analysis**: For any new file generated or introduced during a build, task, or integration, the agent must proactively analyze if it contains local configuration, build-specific outputs, or potentially sensitive credentials, and add it to `.gitignore` if necessary.
- **Ignore Tauri Sidecar Executables (`apps/web/src-tauri/binaries/crm-*`)**: Ensure target-specific built binaries/sidecars copied by build scripts (like `crm-server-*` and `crm-tray-*`) are ignored in `.gitignore`, as they are dynamic compiled artifacts.
