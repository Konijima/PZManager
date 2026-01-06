import os
import shutil
import json
import re
import subprocess
from .const import *
from .utils import print_header, run_cmd, InteractiveMenu, safe_input

def ensure_steamcmd(mgr):
    steam_sh = os.path.join(mgr.config["steamcmd_dir"], "steamcmd.sh")
    if not os.path.exists(steam_sh):
        print(f"{C_YELLOW}Installing SteamCMD...{C_RESET}")
        os.makedirs(mgr.config["steamcmd_dir"], exist_ok=True)
        url = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
        run_cmd(f"curl -sqL \"{url}\" | tar zxvf - -C \"{mgr.config['steamcmd_dir']}\"", shell=True, interactive=mgr.interactive)

def install_server(mgr):
    while True:
        branch = mgr.config.get("branch", "unstable")
        
        def info():
            return f"Install Dir: {mgr.config['install_dir']}\nSelected Branch: {branch}"

        items = [
            (f"Install / Update (Branch: {branch})", '1'),
            ("Verify Integrity (Force Validation)", '2'),
            ("Change Branch", '3'),
            ("Back", 'b')
        ]
        
        menu = InteractiveMenu(items, title="Server Installation", info_text=info)
        c = menu.show()
        
        if c == 'b' or c is None: return
        elif c == '1':
            execute_steam_update(mgr, branch, validate=False)
        elif c == '2':
            execute_steam_update(mgr, branch, validate=True)
        elif c == '3':
            select_branch_menu(mgr)

def select_branch_menu(mgr):
    current = mgr.config.get("branch", "unstable")
    
    # Options
    items = [
        ("Fetch Branches from Steam", 'fetch'),
        ("Enter Branch Manually", 'manual'),
        ("Back", 'b')
    ]
    
    menu = InteractiveMenu(items, title="Select Branch")
    c = menu.show()
    
    if c == 'fetch':
        branches = fetch_branches(mgr)
        if branches:
            # Create selection menu
            b_items = [(b, b) for b in branches]
            b_items.sort()
            # Move public and unstable to top if exist
            for known in ['public', 'unstable', 'b41multiplayer']:
                for i, (name, val) in enumerate(b_items):
                    if name == known:
                        b_items.insert(0, b_items.pop(i))
            
            b_items.append(("Back", 'b'))
            
            sel_menu = InteractiveMenu(b_items, title="Available Branches")
            new_branch = sel_menu.show()
            if new_branch and new_branch != 'b':
                mgr.config["branch"] = new_branch
                mgr.save_config()
                print(f"Branch set to {new_branch}")
                mgr.wait_input()
        else:
            print("Could not fetch branches or none found.")
            mgr.wait_input()
    elif c == 'manual':
        val = safe_input(f"Enter Branch Name (e.g. public, unstable, b41multiplayer) [{current}]: ")
        if val:
            mgr.config["branch"] = val.strip()
            mgr.save_config()

def fetch_branches(mgr):
    print("Fetching branches from Steam (this takes a few seconds)...")
    ensure_steamcmd(mgr)
    steam_cmd = os.path.join(mgr.config["steamcmd_dir"], "steamcmd.sh")
    
    try:
        # app_info_print 380870
        cmd = [
            steam_cmd,
            "+login", "anonymous",
            "+app_info_update", "1",
            "+app_info_print", APP_ID,
            "+quit"
        ]
        # Run and capture. This can be verbose.
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return parse_branches_from_vdf(res.stdout)
    except Exception as e:
        print(f"Error fetching branches: {e}")
        return []

def parse_branches_from_vdf(text):
    # Rudimentary VDF parsing to find "branches" block
    if not text: return []
    
    # regex to find "branches" followed accurately by {
    # We strip whitespace to be safe
    
    # 1. Try to find the branches block
    m = re.search(r'"branches"\s*\{', text)
    if not m: 
        # Fallback: sometimes the dedicated server app info structure is slightly different
        return []
    
    start_idx = m.end()
    
    # block extraction
    open_braces = 1
    idx = start_idx
    while open_braces > 0 and idx < len(text):
        if text[idx] == '{': open_braces += 1
        elif text[idx] == '}': open_braces -= 1
        idx += 1
        
    block = text[start_idx : idx-1]
    
    # Find all keys that look like "branch_name" {
    # Exclude complex nested keys if possible, but usually branches are 1 level deep
    keys = re.findall(r'"([^"]+)"\s*\{', block)
    return keys


def execute_steam_update(mgr, branch, validate=False):
    if mgr.interactive: print_header("SteamCMD Update")
    ensure_steamcmd(mgr)
    
    print(f"Target Directory: {mgr.config['install_dir']}")
    print(f"Branch: {branch}")
    print("Starting SteamCMD...")
    
    steam_cmd = os.path.join(mgr.config["steamcmd_dir"], "steamcmd.sh")
    args = [
        steam_cmd,
        "+force_install_dir", mgr.config["install_dir"],
        "+login", "anonymous",
        "+app_update", APP_ID,
        "-beta", branch,
    ]
    if validate:
        args.append("validate")
        
    args.append("+quit")
    
    run_cmd(args, interactive=mgr.interactive)
    configure_server_files(mgr)
    
    # Try to read RCON settings from INI
    detect_rcon_settings(mgr)
    
    print(f"\n{C_GREEN}Operation complete.{C_RESET}")
    mgr.wait_input("Press Enter...")

def detect_rcon_settings(mgr):
    sname = mgr.config.get('server_name', 'servertest')
    ini = os.path.join(mgr.config["install_dir"], f"Zomboid/Server/{sname}.ini")
    if os.path.exists(ini):
        with open(ini, 'r') as f:
            for line in f:
                if line.strip().startswith("RCONPort="):
                    mgr.config["rcon_port"] = int(line.split("=", 1)[1].strip())
                if line.strip().startswith("RCONPassword="):
                    pwd = line.split("=", 1)[1].strip()
                    if pwd: mgr.config["rcon_password"] = pwd
        mgr.save_config()
        print(f"Detected RCON settings from {sname}.ini")

def configure_server_files(mgr):
    print(f"{C_YELLOW}Applying Configuration fixes...{C_RESET}")
    install_dir = mgr.config["install_dir"]
    
    # 1. wrapper script
    src = os.path.join(install_dir, "start-server.sh")
    dst = os.path.join(install_dir, "start-server-steam.sh")
    if os.path.exists(src):
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
    
    # 2. JSON config
    json_file = os.path.join(install_dir, "ProjectZomboid64.json")
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Memory
        updated_vmargs = []
        mem_set = False
        for arg in data.get("vmArgs", []):
            if arg.startswith("-Xmx"):
                updated_vmargs.append(f"-Xmx{mgr.config['memory']}")
                mem_set = True
            else:
                updated_vmargs.append(arg)
        if not mem_set:
            updated_vmargs.append(f"-Xmx{mgr.config['memory']}")
        
        # Steam Enabled
        new_vmargs = []
        steam_found = False
        for arg in updated_vmargs:
            if "-Dzomboid.steam=" in arg:
                new_vmargs.append("-Dzomboid.steam=1")
                steam_found = True
            else:
                new_vmargs.append(arg)
        if not steam_found:
            new_vmargs.append("-Dzomboid.steam=1")
            
        data["vmArgs"] = new_vmargs
        
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Updated {json_file} (Memory: {mgr.config['memory']}, Steam: Enabled)")
