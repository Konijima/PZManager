import os
import sys
import json
import subprocess
import shutil
import time
from .const import *
from .utils import print_header, run_cmd, InteractiveMenu, format_info_box, get_existing_server_names, safe_input
from . import steam_tools
from . import service_tools
from . import scheduler
from . import backup_tools
from .mod_manager import InternalModManager
from .rcon import RCONClient

class PZManager:
    def __init__(self, interactive=True, instance_name=None):
        self.interactive = interactive
        self.global_config = {}
        self.config = {}
        self.current_instance = "default"
        
        self.ensure_struct()
        self.load_global_config()
        
        if instance_name:
            self.load_instance_config(instance_name)
        else:
            # Load the last active instance or default
            tgt = self.global_config.get("last_instance", "default")
            self.load_instance_config(tgt)

    def ensure_struct(self):
        os.makedirs(INSTANCES_DIR, exist_ok=True)
        # Migration: If old config exists and we have no instances, move it
        if os.path.exists(OLD_CONFIG_FILE) and not os.listdir(INSTANCES_DIR):
            print(f"{C_YELLOW}Migrating legacy config to default instance...{C_RESET}")
            shutil.move(OLD_CONFIG_FILE, os.path.join(INSTANCES_DIR, "default.json"))

    def load_global_config(self):
        if os.path.exists(GLOBAL_CONFIG_FILE):
            try:
                with open(GLOBAL_CONFIG_FILE, 'r') as f:
                    self.global_config = json.load(f)
            except: self.global_config = {}
        self.global_config.setdefault("last_instance", "default")
        self.save_global_config()

    def save_global_config(self):
        with open(GLOBAL_CONFIG_FILE, 'w') as f:
            json.dump(self.global_config, f, indent=4)

    def load_instance_config(self, inst_name):
        self.current_instance = inst_name
        p = os.path.join(INSTANCES_DIR, f"{inst_name}.json")
        
        if os.path.exists(p):
            try:
                with open(p, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"{C_RED}Error loading instance '{inst_name}': {e}{C_RESET}")
                self.config = {}
        else:
            self.config = {}
            if inst_name == "default":
                 # If default doesn't exist (fresh install), defaults will set
                 pass
            else:
                 print(f"{C_YELLOW}Creating new instance: {inst_name}{C_RESET}")

        # Set defaults if missing (Same as before)
        self.config.setdefault("install_dir", DEFAULT_INSTALL_DIR)
        self.config.setdefault("steamcmd_dir", DEFAULT_STEAMCMD_DIR)
        self.config.setdefault("backup_dir", DEFAULT_BACKUP_DIR)
        
        # Instance specific defaults - Try to make service/server name match instance if new
        self.config.setdefault("service_name", f"pzserver-{inst_name}" if inst_name != "default" else DEFAULT_SERVICE_NAME)
        self.config.setdefault("server_name", inst_name if inst_name != "default" else DEFAULT_SERVER_NAME)
        
        self.config.setdefault("memory", "4g")
        self.config.setdefault("restart_times", [0, 6, 12, 18]) 
        self.config.setdefault("rcon_host", "127.0.0.1")
        self.config.setdefault("rcon_port", 27015)
        self.config.setdefault("rcon_password", "")
        self.config.setdefault("branch", "unstable")
        self.config.setdefault("auto_backup", True)
        self.config.setdefault("backup_retention", 5)
        self.config.setdefault("enable_mod_update_check", False)
        
        self.save_config()
        
        # Update global last used
        self.global_config["last_instance"] = inst_name
        self.save_global_config()

    def load_config(self):
        # Legacy/Alias wrapper just in case
        self.load_instance_config(self.current_instance)

    def save_config(self):
        p = os.path.join(INSTANCES_DIR, f"{self.current_instance}.json")
        with open(p, 'w') as f:
            json.dump(self.config, f, indent=4)

    def list_instances(self):
        res = []
        if os.path.exists(INSTANCES_DIR):
            for f in os.listdir(INSTANCES_DIR):
                if f.endswith(".json"):
                    res.append(f[:-5])
        return sorted(res)

    def wait_input(self, msg="Press Enter to continue..."):
        if self.interactive:
            safe_input(msg)
            
    # --- Wrappers for Modules ---
    
    def install_server(self):
        steam_tools.install_server(self)
    
    def manage_service_control(self):
        service_tools.manage_service_control(self)
        
    def run_scheduler(self):
        scheduler.run_scheduler(self)

    def main_menu(self):
        last_index = 0
        while True:
            def info():
                sched_svc = self.config['service_name'] + "-scheduler"
                is_active = False
                try:
                    out = subprocess.run(f"systemctl is-active {sched_svc}", shell=True, capture_output=True, text=True).stdout.strip()
                    is_active = (out == "active")
                except: pass
                
                next_restart = scheduler.get_next_restart_info(self) if is_active else "Scheduler Inactive"
                
                return format_info_box({
                    "Active Instance": f"{C_BOLD}{self.current_instance}{C_RESET}",
                    "Server Dir": self.config['install_dir'],
                    "Service": self.config['service_name'],
                    "Next Restart": next_restart,
                    "Branch": self.config['branch']
                })
            
            # Check if installed
            is_installed = os.path.exists(os.path.join(self.config['install_dir'], "ProjectZomboid64.json"))
            install_label = "Update Server" if is_installed else "Install Server"
            
            items = [
                (f"Server Control", '1', "Start, Stop, Restart service, view logs and manage the Scheduler."),
                ("Player Management", '7', "View online players, kick users, ban griefers, and broadcast messages."),
                ("Mod Manager", '3', "Search, install, and update Steam Workshop mods."),
                ("Configuration", '2', "Adjust memory (RAM), restart schedules, RCON, and automation settings."),
                ("Backup & Restore", '5', "Create manual backups or restore from previous points."),
                ("Instance Manager", '4', "Create or switch between different server profiles (e.g. Hardcore/Casual)."),
                (install_label, '6', f"Install or Update the server files to branch '{self.config['branch']}')."),
                ("Quit", 'q', "Exit PZ Manager.")
            ]

            if not self.interactive:
                print("Interactive mode required for menu.")
                sys.exit(1)

            menu = InteractiveMenu(items, title="Main Menu", info_text=info, default_index=last_index)
            choice = menu.show()
            last_index = menu.selected

            if choice == '1': self.manage_service_control()
            elif choice == '2': self.submenu_config()
            elif choice == '3': self.manage_mods()
            elif choice == '4': self.submenu_instances()
            elif choice == '5': self.submenu_backup()
            elif choice == '6': self.install_server()
            elif choice == '7': self.submenu_players()
            elif choice == 'q' or choice is None:
                print("Bye.")
                sys.exit(0)

    def submenu_players(self):
        rcon = RCONClient(self.config["rcon_host"], self.config["rcon_port"], self.config["rcon_password"])
        
        while True:
            # Try to fetch players
            if not rcon.sock and not rcon.connect():
                 print(f"{C_RED}Failed to connect to RCON. Is server running?{C_RESET}")
                 self.wait_input()
                 return
                 
            try:
                raw_players = rcon.get_players() # returns list of dict
                # [{"name": "Konijima"}]
            except Exception as e:
                print(f"RCON Error: {e}")
                self.wait_input()
                return

            def info():
                c = len(raw_players)
                return format_info_box({
                    "Online Players": str(c),
                    "RCON Status": f"{C_GREEN}Connected{C_RESET}"
                })

            items = []
            items.append(("Refresh", "refresh"))
            items.append(("Broadcast Message", "broadcast"))
            items.append((f"{C_YELLOW}--- Online Players ---{C_RESET}", None))

            for p in raw_players:
                n = p.get("name", "Unknown")
                items.append((f"{n}", n))
            
            if not raw_players:
                items.append(("(No players online)", None))
            
            items.append(("Back", "back"))

            menu = InteractiveMenu(items, title="Player Management", info_text=info)
            choice = menu.show() # choice is the 'value' of the tuple

            if choice == 'back' or choice is None:
                rcon.quit()
                return
            elif choice == 'refresh':
                continue
            elif choice == 'broadcast':
                msg = safe_input("Enter message: ")
                if msg:
                    rcon.broadcast(msg)
                    print("Message sent.")
                    time.sleep(1)
            else:
                # Player selected
                self.submenu_player_actions(rcon, choice)

    def submenu_player_actions(self, rcon, player_name):
        while True:
            items = [
                (f"Kick {player_name}", 'kick'),
                (f"Ban {player_name}", 'ban'),
                ("Back", 'b')
            ]
            m = InteractiveMenu(items, title=f"Actions for {player_name}")
            c = m.show()
            
            if c == 'b' or c is None: return
            elif c == 'kick':
                reason = safe_input("Reason (optional): ")
                rcon.kick(player_name, reason if reason else "Kicked by Admin")
                print(f"Kicked {player_name}")
                time.sleep(1)
                return
            elif c == 'ban':
                reason = safe_input("Reason (optional): ")
                rcon.ban(player_name, reason=reason if reason else "Banned by Admin")
                print(f"Banned {player_name}")
                time.sleep(1)
                return

    def submenu_instances(self):
        last_index = 0
        while True:
            instances = self.list_instances()
            
            def info_func():
                return format_info_box({
                    "Current Instance": self.current_instance,
                    "Total Instances": str(len(instances)),
                    "List": ", ".join(instances)
                })

            items = [
                ("Switch Active Instance", 'switch', "Change the server profile you are currently managing."),
                ("Create New Instance", 'create', "Setup a new separate server profile (e.g. for different settings/saves)."),
                ("Import Existing Servers", 'detect', "Scan the installation directory for unmanaged server config files."),
                ("Back", 'b', "Return to Main Menu.")
            ]
            
            menu = InteractiveMenu(items, title="Manage Instances", info_text=info_func, default_index=last_index)
            choice = menu.show()
            last_index = menu.selected
            
            if choice == 'b' or choice == 'q' or choice is None: return
            elif choice == 'switch':
                switch_items = []
                for inst in instances:
                    label = f"{inst} {C_GREEN}(Active){C_RESET}" if inst == self.current_instance else inst
                    switch_items.append((label, inst))
                
                switch_items.append(("Cancel", 'cancel'))
                
                # Default to current instance index
                def_idx = 0
                if self.current_instance in instances:
                    def_idx = instances.index(self.current_instance)
                
                sm = InteractiveMenu(switch_items, title="Switch Instance", default_index=def_idx)
                s_choice = sm.show()
                
                if s_choice and s_choice != 'cancel':
                    self.load_instance_config(s_choice)
            
            elif choice == 'create':
                print_header("Create Instance")
                name = safe_input("Enter new instance name (alphanumeric, no spaces): ")
                if name:
                    name = name.strip()
                    if name and name.isalnum():
                        if name in instances:
                            print("Instance already exists.")
                            self.wait_input()
                        else:
                            self.load_instance_config(name)
                            print(f"Created and switched to {name}")
                            self.wait_input()
                    else:
                        print("Invalid name.")
                        self.wait_input()
            
            elif choice == 'detect':
                found = get_existing_server_names(self.config['install_dir'])
                print_header("Import Servers")
                print("Scanning Zomboid/Server/ for .ini files...")
                imported_count = 0
                for f in found:
                    if f not in instances:
                        print(f" - Found unmanaged server: {f}")
                        yn_raw = safe_input(f"   Import as instance '{f}'? [y/N]: ")
                        yn = yn_raw.lower() if yn_raw else ''
                        if yn == 'y':
                            # Create a config for it
                            prev = self.current_instance
                            self.load_instance_config(f)
                            # Custom overrides for imported
                            self.config['server_name'] = f
                            self.config['service_name'] = f"pzserver-{f}"
                            self.save_config()
                            print(f"   Imported {f}.")
                            imported_count += 1
                            # Revert to previous
                            if prev != f:
                                self.load_instance_config(prev)
                
                if imported_count == 0:
                    print("No new servers to import.")
                else:
                    print(f"\nImported {imported_count} instances.")
                self.wait_input()

    def submenu_config(self):
        last_index = 0
        while True:
            def info():
                return format_info_box({
                    "Server Name": self.config['server_name'],
                    "Current Memory": self.config['memory'],
                    "Restart Schedule": str(self.config['restart_times']),
                    "Auto Backup": str(self.config.get("auto_backup", True)),
                    "Backup Retention": str(self.config.get("backup_retention", 5)),
                    "Mod Update Check": str(self.config.get("enable_mod_update_check", False))
                })

            sname = self.config['server_name']
            items = [
                (f"Edit Server Settings (.ini)", '1', f"Edit {sname}.ini (Public settings, PW, etc)."),
                (f"Edit Sandbox Options (.lua)", '2', f"Edit {sname}_SandboxVars.lua (Gameplay settings)."),
                (f"Memory Allocation", '3', f"Current Limit: {self.config['memory']}. Adjust RAM for the server process."),
                (f"Restart Schedule", '4', "Set times for automated daily restarts (e.g. 0, 6, 12, 18)."),
                (f"Auto Backup", 'toggle_backup', f"State: {self.config.get('auto_backup', True)}. Toggle backups before scheduled restarts."),
                (f"Backup Retention", 'set_retention', f"Keep last {self.config.get('backup_retention', 5)} backups. Clean older ones."),
                (f"Mod Update Check", 'toggle_mod_check', f"State: {str(self.config.get('enable_mod_update_check', False))}. Auto-restart if mods update on Workshop."),
                (f"RCON Connection", '5', "Configure IP/Port/Password for remote console access."),
                ("Back", 'b', "Return to Main Menu.")
            ]

            menu = InteractiveMenu(items, title="Configuration", info_text=info, default_index=last_index)
            choice = menu.show()
            last_index = menu.selected

            if choice == 'b' or choice == 'q' or choice is None: return
            elif choice == '1':
                p = os.path.join(self.config['install_dir'], f"Zomboid/Server/{self.config['server_name']}.ini")
                run_cmd(f"nano {p}", shell=True)
            elif choice == '2':
                p = os.path.join(self.config['install_dir'], f"Zomboid/Server/{self.config['server_name']}_SandboxVars.lua")
                run_cmd(f"nano {p}", shell=True)
            elif choice == '3':
                val = safe_input(f"Enter memory (e.g. 4g, 8192m) [Current: {self.config['memory']}]: ")
                if val:
                    self.config['memory'] = val
                    self.save_config()
                    steam_tools.configure_server_files(self)
            elif choice == '4':
                print(f"Current Schedule: {self.config['restart_times']}")
                val = safe_input("Enter hours (comma separated, e.g. 0,6,12,18): ")
                if val:
                    try:
                        self.config['restart_times'] = [int(x.strip()) for x in val.split(",")]
                        self.save_config()
                    except:
                        print("Invalid format.")
                        self.wait_input()
            elif choice == 'toggle_backup':
                curr = self.config.get("auto_backup", True)
                self.config["auto_backup"] = not curr
                self.save_config()
            elif choice == 'set_retention':
                val = safe_input(f"Enter retention count (Default 5) [Current: {self.config.get('backup_retention', 5)}]: ")
                if val and val.isdigit():
                    self.config["backup_retention"] = int(val)
                    self.save_config()
            elif choice == 'toggle_mod_check':
                curr = self.config.get("enable_mod_update_check", False)
                self.config["enable_mod_update_check"] = not curr
                self.save_config()
            elif choice == '5':
                self.submenu_rcon()

    def submenu_rcon(self):
        last_index = 0
        while True:
            def info():
                return format_info_box({
                    "Host": self.config['rcon_host'],
                    "Port": str(self.config['rcon_port']),
                    "Password": '*' * len(self.config['rcon_password']) if self.config['rcon_password'] else '(None)'
                })

            items = [
                ("Change Host", '1'),
                ("Change Port", '2'),
                ("Change Password", '3'),
                ("Back", 'b')
            ]
            
            menu = InteractiveMenu(items, title="RCON Settings", info_text=info, default_index=last_index)
            c = menu.show()
            last_index = menu.selected

            if c == 'b' or c == 'q' or c is None: return
            elif c == '1':
                val = safe_input(f"Host [{self.config['rcon_host']}]: ")
                if val: 
                    self.config['rcon_host'] = val
                    self.save_config()
            elif c == '2':
                val = safe_input(f"Port [{self.config['rcon_port']}]: ")
                if val:
                    try:
                        self.config['rcon_port'] = int(val)
                        self.save_config()
                    except: pass
            elif c == '3':
                val = safe_input("Password: ")
                if val is not None: # Empty password allowed?
                    self.config['rcon_password'] = val
                    self.save_config()



    def submenu_backup(self):
        last_index = 0
        while True:
            def info():
                files = backup_tools.get_recent_backups(self)
                data = {"Backup Directory": self.config['backup_dir']}
                
                if not files:
                    data["Status"] = "No backups found"
                else:
                    data["Total Backups"] = str(len(files))
                    # List top 5
                    for i, f in enumerate(files[:5]):
                        size = os.path.getsize(f) / (1024 * 1024) # MB
                        dt = os.path.getmtime(f)
                        date_str = backup_tools.datetime.fromtimestamp(dt).strftime("%Y-%m-%d %H:%M")
                        fname = os.path.basename(f)
                        data[f"#{i+1}"] = f"{fname} ({size:.1f} MB) - {date_str}"
                
                return format_info_box(data)

            items = [
                ("Create Backup", '1'),
                ("Manage Backups (Restore/Delete)", '2'),
                ("Back", 'b')
            ]
            menu = InteractiveMenu(items, title="Backup / Restore", info_text=info, default_index=last_index)
            c = menu.show()
            last_index = menu.selected

            if c == 'b' or c == 'q' or c is None: return
            elif c == '1': backup_tools.backup_data(self)
            elif c == '2': backup_tools.manage_backups_menu(self)

    def manage_mods(self):
        # Initialize internal mod manager if needed
        mm = InternalModManager(self.config['install_dir'], self.config['steamcmd_dir'], self.config.get('server_name', 'servertest'))
        mm.run()


