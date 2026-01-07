# PZ Manager

**PZ Manager** is a lightweight Python CLI tool for managing Project Zomboid Dedicated Servers on Linux. It handles multiple server instances, automation, backup, and mod management with ease.

Designed to work seamlessly with the [ResetZone Mod](https://github.com/Konijima/ResetZone).

## ✨ Features

*   **Multi-Instance Support**: Run multiple servers with isolated configs and saves.
*   **Service Management**: Auto-generate `systemd` services for your servers.
*   **Mod Manager**: Search, install, and update Steam Workshop mods directly.
*   **Auto-Updater**: Automatically checks for mod updates via Steam API and schedules restarts.
*   **Scheduler**: Automated restarts, backups, and player warnings via RCON.
*   **Backups**: Configurable manual and automated backup system.
*   **RCON Client**: Send commands to your server directly from the CLI.

---

## 📋 Prerequisites

*   Linux OS (Debian/Ubuntu recommended)
*   Python 3.6+
*   `curl` (for SteamCMD)
*   `sudo` access

**Install dependencies:**
```bash
sudo apt update && sudo apt install python3 curl -y
```

---

## ⚙️ Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Konijima/PZManager.git
    cd PZManager
    ```

2.  **Make executable:**
    ```bash
    chmod +x pz_manager.py
    ```

3.  **Link to PATH (Optional):**
    Allows running `pz_manager` from anywhere.
    ```bash
    sudo ln -sf "$(pwd)/pz_manager.py" /usr/local/bin/pz_manager
    ```

4.  **First Run:**
    Initialize configuration and install SteamCMD.
    ```bash
    pz_manager
    ```

---

## 🚀 Usage

### Interactive Mode
Run the tool without arguments to enter the main menu:
```bash
pz_manager
```

### CLI Shortcuts
Manage the **currently active instance** directly from the terminal:

| Command | Description |
| :--- | :--- |
| `pz_manager start` | Start the server service |
| `pz_manager stop` | Stop the server service |
| `pz_manager restart` | Restart the server service |
| `pz_manager status` | Check service status |
| `pz_manager logs` | View live server logs |
| `pz_manager backup` | Trigger a manual backup |
| `pz_manager install` | Install/Update server files |

---

## 🛠️ Configuration & Automation

### Scheduler Service
The scheduler handles automated tasks like restarts and updates.
*   **Setup**: Use the "Service Management" menu option to create the scheduler service.
*   **Mod Updates**: The scheduler automatically checks Steam Workshop for mod updates every 15 minutes.
*   **Restarts**: Configurable restart intervals (e.g., every 6 hours) with in-game warnings.

### Instance Configuration
Each instance has its own configuration stored in `config/`.
*   **Switch Instance**: Use the top menu in interactive mode.
*   **New Instance**: Creates a new folder structure and systemd service name.
