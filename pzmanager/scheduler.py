import os
import time
import subprocess
from datetime import datetime, timedelta
from .const import LOGS_DIR
from .rcon import RCONClient
from . import backup_tools
from .update_checker import ModUpdateChecker

def log_scheduler_event(instance_name, msg):
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, f"scheduler_{instance_name}.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception as e:
        print(f"Logging failed: {e}")

def get_next_restart_info(mgr):
    restart_times = mgr.config.get("restart_times", [0, 6, 12, 18])
    if not restart_times: return "Not Scheduled"
    
    now = datetime.now()
    current_hour = now.hour
    current_min = now.minute
    
    # Calculate next restart
    min_diff = 9999
    
    for h in restart_times:
        diff = (h * 60) - ((current_hour * 60) + current_min)
        if diff <= 0: diff += 24 * 60
        if diff < min_diff: min_diff = diff
            
    hours_left = min_diff // 60
    mins_left = min_diff % 60
    
    dt_next = now + timedelta(minutes=min_diff)
    time_str = dt_next.strftime("%H:%M")
    
    return f"{time_str} (in {hours_left}h {mins_left}m)"

def restart_service_process(mgr, inst):
    # Core restart logic
    svc = mgr.config["service_name"]
    
    print("[Scheduler] Stopping service...")
    subprocess.run(f"sudo systemctl stop {svc}", shell=True)
    log_scheduler_event(inst, "Service stopped.")
    
    # Auto Backup
    if mgr.config.get("auto_backup", True):
        try:
            backup_tools.perform_auto_backup(mgr)
            log_scheduler_event(inst, "Auto-backup completed successfully.")
        except Exception as e:
            print(f"[Scheduler] Auto-backup failed: {e}")
            log_scheduler_event(inst, f"Auto-backup FAILED: {e}")
            
    # Cleanup Map
    perform_map_cleanup(mgr)
    
    print("[Scheduler] Starting service...")
    subprocess.run(f"sudo systemctl start {svc}", shell=True)
    log_scheduler_event(inst, "Service restart command issued.")

def perform_map_cleanup(mgr):
    print("[Scheduler] Performing Map Cleanup...")
    install_dir = mgr.config['install_dir']
    inst = mgr.current_instance
    
    list_file = os.path.join(install_dir, "Zomboid/Lua/reset_zones.txt")
    if not os.path.exists(list_file):
        list_file = os.path.join(install_dir, "Zomboid/reset_zones.txt")
    
    if not os.path.exists(list_file):
            msg = f"List file not found at {list_file}. Skipping cleanup."
            print(f"[Scheduler] {msg}")
            log_scheduler_event(inst, msg)
            return

    save_dir = os.path.join(install_dir, f"Zomboid/Saves/Multiplayer/{mgr.config['server_name']}")
    if not os.path.exists(save_dir):
        msg = f"Save dir not found: {save_dir}"
        print(f"[Scheduler] {msg}")
        log_scheduler_event(inst, msg)
        return
        
    try:
        with open(list_file, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[Scheduler] Failed to read reset_zones: {e}")
        return
        
    count = 0
    for line in lines:
        xy = line.strip() # "10_10"
        if not xy: continue
        
        # Targets
        targets = [
            f"map_{xy}.bin",
            f"chunkdata_{xy}.bin",
            f"zpop_{xy}.bin"
        ]
        
        for t in targets:
            p = os.path.join(save_dir, t)
            if os.path.exists(p):
                try:
                    os.remove(p)
                    count += 1
                except Exception as e:
                    print(f"Failed to delete {t}: {e}")
                    
    msg = f"Cleanup Complete. Deleted {count} map/chunk files."
    print(f"[Scheduler] {msg}")
    log_scheduler_event(inst, msg)

def trigger_mod_restart_sequence(mgr, rcon):
    # 5 Minute countdown
    inst = mgr.current_instance
    log_scheduler_event(inst, "Initiating Mod Update Restart Sequence (5 min)")
    
    if rcon.sock is None: rcon.connect()
    
    for i in range(5, 0, -1):
        msg = f"WARNING: Critical Mod Update Detected! Restart in {i} minutes."
        print(f"[Scheduler] {msg}")
        if rcon.sock: rcon.broadcast(msg)
        time.sleep(60)
        
    if rcon.sock:
        rcon.broadcast("Server restarting for updates NOW...")
        time.sleep(5)
        rcon.quit()
        
    restart_service_process(mgr, inst)

def run_scheduler(mgr):
    print(f"[Scheduler] Starting for instance: {mgr.config['server_name']}")
    log_scheduler_event(mgr.current_instance, "Scheduler service started.")
    
    update_checker = ModUpdateChecker(mgr)
    last_mod_check = 0
    mod_check_interval = 15 * 60 # 15 mins
    
    while True:
        try:
            now = datetime.now()
            current_hour = now.hour
            current_min = now.minute
            inst = mgr.current_instance
            
            # --- 1. SCHEDULED RESTART LOGIC ---
            restart_times = mgr.config.get("restart_times", [0, 6, 12, 18])
            min_diff = 9999
            for h in restart_times:
                diff = (h * 60) - ((current_hour * 60) + current_min)
                if diff <= 0: diff += 24 * 60
                if diff < min_diff: min_diff = diff
            
            rcon = RCONClient(mgr.config["rcon_host"], mgr.config["rcon_port"], mgr.config["rcon_password"])
            
            # Warnings
            if min_diff in [60, 30, 10, 5, 1]:
                print(f"[Scheduler] Warning: Restart in {min_diff} min")
                rcon.connect()
                if rcon.sock:
                    rcon.broadcast(f"WARNING: Scheduled Restart in {min_diff} minutes!")
                    rcon.quit()

            # Execute Scheduled Restart
            if min_diff <= 0: # It matches exactly
                log_scheduler_event(inst, "Scheduled time reached. Restarting.")
                rcon.connect()
                if rcon.sock:
                    rcon.broadcast("Server restarting NOW for Scheduled Maintenance...")
                    time.sleep(5)
                    rcon.quit()
                
                restart_service_process(mgr, inst)
                time.sleep(65) # Skip past this minute
                continue

            # --- 2. MOD UPDATE LOGIC ---
            if mgr.config.get("enable_mod_update_check", False):
                if time.time() - last_mod_check > mod_check_interval:
                    last_mod_check = time.time()
                    print("[Scheduler] Checking for mod updates...")
                    has_updates, updates = update_checker.check()
                    
                    if has_updates:
                        msg = f"Mod updates detected for IDs: {updates}"
                        print(f"[Scheduler] {msg}")
                        log_scheduler_event(inst, msg)
                        
                        trigger_mod_restart_sequence(mgr, rcon) # This takes 5 mins
                        time.sleep(60) 
                        continue
                        
        except Exception as e:
            print(f"[Scheduler] Loop Error: {e}")
            log_scheduler_event(mgr.current_instance, f"Loop Error: {e}")
        
        time.sleep(60)
