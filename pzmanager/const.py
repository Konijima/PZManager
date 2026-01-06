import os

# --- Constants & Defaults ---
APP_ID = "108600" # Project Zomboid Dedicated Server
BRANCH = "unstable" # Build 42
DEFAULT_INSTALL_DIR = os.path.expanduser("~/pzserver")
DEFAULT_STEAMCMD_DIR = os.path.expanduser("~/steamcmd")
DEFAULT_BACKUP_DIR = os.path.expanduser("~/pzbackups")
DEFAULT_SERVICE_NAME = "pzserver"
DEFAULT_SERVER_NAME = "servertest"
CONFIG_DIR = os.path.expanduser("~/.config/pz_manager")
GLOBAL_CONFIG_FILE = os.path.join(CONFIG_DIR, "global.json")
INSTANCES_DIR = os.path.join(CONFIG_DIR, "instances")
LOGS_DIR = os.path.join(CONFIG_DIR, "logs")
# Deprecated but kept for migration check
OLD_CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ANSI Colors
C_RESET = "\033[0m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
