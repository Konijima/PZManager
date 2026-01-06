# PZ Manager Documentation

**PZ Manager** is a powerful Python-based command-line interface (CLI) for managing Project Zomboid Dedicated Servers on Linux. It simplifies server installation, mod management, automation, and multi-instance handling.

## 🚀 Key Features

*   **Multi-Instance Support:** Run multiple separate server instances (e.g., specific modpacks, difficulties) on the same machine with independent configurations and saves.
*   **Mod Management:** Search, download, and enable Steam Workshop mods directly from the CLI. Handles Mod IDs and Workshop IDs automatically.
*   **Automated Scheduler:** A dedicated background service that handles:
    *   Scheduled Restarts (with RCON warnings to players).
    *   Automatic Backups before restarts.
    *   Map Cleanup (Reset Zones) integration.
*   **Service Management:** seamless integration with `systemd` to run your server and scheduler as background services.
*   **Backup System:** Manual and automated backups with configurable retention policies.
*   **RCON Client:** Built-in RCON client for sending commands and broadcasts.

---

## 💻 CLI Usage

Once installed, you can launch the interactive menu by running:
```bash
pz_manager
```

### Shortcuts
You can also pass arguments for quick actions on the *currently active instance*:

```bash
pz_manager start       # Start the server service
pz_manager stop        # Stop the server service
pz_manager restart     # Restart the server service
pz_manager status      # Check service status
```

---

## 🛠️ Interactive Menu Guide

### 1. Instance Management
The top bar shows your **Current Instance** (e.g., `default`, `hardcore`).
*   **Switch Instance:** Change the active server context.
*   **Create New Instance:** Set up a fresh server profile. Each instance has its own:
    *   Server Name & Config (`.ini`, `_SandboxVars.lua`)
    *   Save Files
    *   Service File (`pzserver-{name}`)
    *   Scheduler Logs

### 2. Install / Update
*   Downloads the Project Zomboid Dedicated Server files via SteamCMD.
*   Validates files and handles updates.

### 3. Mod Manager
A comprehensive tool for managing content:
*   **List Installed Mods:** See what is currently enabled.
*   **Add Mod (Search/ID):** Type a name to search Workshop or paste an ID.
    *   *Note: This updates both `WorkshopItems` and `Mods` lines in your server config.*
*   **Update Mods:** Forces a generic update of workshop content.
*   **Remove Mod:** Cleanly removes entries from config.

### 4. Service Control
Manage the background processes for your current instance.
*   **Start/Stop/Restart:** Control the game server.
*   **View Console Logs:** Tail the systemd journal for the game server.
*   **View Scheduler Logs:** View independent audit logs for restarts, backups, and map resets (`~/.config/pz_manager/logs/`).
*   **Install/Uninstall Service:** Create the `systemd` unit files for the Game Server and the Scheduler.

### 5. Backup Manager
*   **Create Backup:** Manual snapshot of the `Zomboid` save directory.
*   **Restore:** Rollback to a previous state (Warning: Overwrites current data).
*   **Manage:** Delete old backups.
*   *Backups are stored in `~/pzbackups` by default, named by instance.*

### 6. Configuration
Edit settings for the active instance:
*   **Edit .ini / SandboxVars:** Opens `nano` for the config files.
*   **Memory Limit:** Set JVM heap size (e.g., `8g`).
*   **Restart Schedule:** Define restart hours (e.g., `0, 6, 12, 18`).
*   **Auto Backup:** Toggle backups on restart.
*   **Retention:** How many backups to keep.

---

## 📂 File Structure & Configuration

### Configuration Files
PZ Manager stores its metadata in `~/.config/pz_manager/`:
*   `instances/`: JSON files for each instance (e.g., `default.json`, `pvp.json`).
*   `logs/`: Scheduler audit logs.
*   `global.json`: Stores the last active instance.

### Instance Config Example (`default.json`)
```json
{
    "install_dir": "/home/user/pzserver",
    "server_name": "servertest",
    "memory": "4g",
    "restart_times": [0, 6, 12, 18],
    "auto_backup": true,
    "rcon_port": 27015
}
```

### Server Data
By default, game data follows standard PZ paths:
*   **Config:** `~/pzserver/Zomboid/Server/`
*   **Saves:** `~/pzserver/Zomboid/Saves/Multiplayer/`
*   **Steam Workshop:** `~/steamcmd/steamapps/workshop/content/108600/`
