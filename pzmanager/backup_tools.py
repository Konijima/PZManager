import os
import glob
from datetime import datetime
from .const import *
from .utils import print_header, run_cmd, InteractiveMenu, safe_input

def get_recent_backups(mgr):
    b_dir = mgr.config.get("backup_dir", DEFAULT_BACKUP_DIR)
    if not os.path.exists(b_dir):
        return []
    
    inst = mgr.current_instance
    # Sort by mtime descending. Filter for current instance.
    # Pattern: pz_backup_{inst}_*.tar.gz
    # Use glob pattern to filter automatically
    pattern = os.path.join(b_dir, f"pz_backup_{inst}_*.tar.gz")
    files = glob.glob(pattern)
    
    # Backwards compatibility: If instance is 'default', also include old non-prefixed backups?
    # Or strict separation? Let's go with strict separation to encourage migration, 
    # but maybe we should display ALL only if specific flag? 
    # For now, stick to instance specific to prevent confusion.
    
    files.sort(key=os.path.getmtime, reverse=True)
    return files

def backup_data(mgr):
    if mgr.interactive: print_header("Backup")
    data_dir = os.path.join(mgr.config["install_dir"], "Zomboid")
    if not os.path.exists(data_dir):
        print(f"Data directory not found: {data_dir}")
        mgr.wait_input("Press Enter...")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(mgr.config["backup_dir"], exist_ok=True)
    
    inst = mgr.current_instance
    fname = f"pz_backup_{inst}_{ts}.tar.gz"
    
    dest = os.path.join(mgr.config["backup_dir"], fname)
    
    print(f"Backing up {data_dir}...")
    parent = os.path.dirname(data_dir)
    base = os.path.basename(data_dir)
    run_cmd(["tar", "-czf", dest, "-C", parent, base], interactive=mgr.interactive)
    print(f"Backup saved to {dest}")
    mgr.wait_input("Press Enter...")

def manage_backups_menu(mgr):
    files = get_recent_backups(mgr)
    
    if not files:
        if mgr.interactive:
            print_header("Manage Backups")
            print("No backup files found.")
            mgr.wait_input("Press Enter...")
        return
        
    items = []
    for f in files:
        fname = os.path.basename(f)
        size = os.path.getsize(f) / (1024 * 1024)
        items.append((f"{fname} ({size:.1f} MB)", f))
    items.append(("Back", 'b'))
    
    menu = InteractiveMenu(items, title="Select Backup to Manage")
    backup_file = menu.show()
    
    if backup_file == 'b' or backup_file is None: return
    
    # Submenu for Action
    action_items = [
        ("Restore this Backup", 'restore'),
        ("Delete this Backup", 'delete'),
        ("Back", 'b')
    ]
    fname = os.path.basename(backup_file)
    action_menu = InteractiveMenu(action_items, title=f"Action for {fname}")
    action = action_menu.show()
    
    if action == 'restore':
        process_restore(mgr, backup_file)
    elif action == 'delete':
        process_delete(mgr, backup_file)

def process_restore(mgr, backup_file):
    data_dir = os.path.join(mgr.config["install_dir"], "Zomboid")
    parent = os.path.dirname(data_dir)
    
    print_header("Restore Confirmation")
    print(f"Restoring: {C_BOLD}{os.path.basename(backup_file)}{C_RESET}")
    print(f"{C_RED}WARNING: This will overwrite data in:{C_RESET}")
    print(f"{data_dir}")
    
    val = safe_input(f"\n{C_YELLOW}Are you sure? (type 'yes' to confirm): {C_RESET}")
    if (val or "").lower() == 'yes':
        os.makedirs(parent, exist_ok=True)
        run_cmd(["tar", "-xzf", backup_file, "-C", parent], interactive=mgr.interactive)
        print("Restore complete.")
        mgr.wait_input("Press Enter...")

def process_delete(mgr, backup_file):
    print_header("Delete Confirmation")
    print(f"Deleting: {C_BOLD}{os.path.basename(backup_file)}{C_RESET}")
    
    val = safe_input(f"\n{C_RED}Are you sure you want to delete this file? (yes/no): {C_RESET}")
    if (val or "").lower() == 'yes':
        try:
            os.remove(backup_file)
            print("Deleted.")
        except Exception as e:
            print(f"Error: {e}")
        mgr.wait_input("Press Enter...")

def cleanup_old_backups(mgr):
    retention = mgr.config.get("backup_retention", 5)
    files = get_recent_backups(mgr)
    if len(files) > retention:
        to_del = files[retention:]
        print(f"[Backup] Cleaning up {len(to_del)} old backups (Retention: {retention})...")
        for f in to_del:
            try:
                os.remove(f)
                print(f"  Deleted {os.path.basename(f)}")
            except Exception as e:
                print(f"  Failed to delete {f}: {e}")

def perform_auto_backup(mgr):
    if not mgr.config.get("auto_backup", True):
        return
        
    print("[Backup] Performing Auto-Backup...")
    # Modified backup logic for non-interactive / minimal output
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(mgr.config["backup_dir"], exist_ok=True)
    
    inst = mgr.current_instance
    fname = f"pz_backup_{inst}_auto_{ts}.tar.gz"
    
    dest = os.path.join(mgr.config["backup_dir"], fname)
    data_dir = os.path.join(mgr.config["install_dir"], "Zomboid")
    
    if not os.path.exists(data_dir):
        print(f"[Backup] Data dir {data_dir} missing. Skipping.")
        return

    parent = os.path.dirname(data_dir)
    base = os.path.basename(data_dir)
    
    # Run silently-ish
    run_cmd(["tar", "-czf", dest, "-C", parent, base], check=False, interactive=False)
    print(f"[Backup] Saved to {dest}")
    
    cleanup_old_backups(mgr)

