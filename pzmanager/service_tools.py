import os
import sys
import subprocess
from .const import *
from .utils import print_header, run_cmd, InteractiveMenu, clear_screen, format_info_box, safe_input

def manage_service_control(mgr):
    last_idx = 0
    while True:
        svc = mgr.config["service_name"]
        sched_svc = svc + "-scheduler"
        
        svc_installed = os.path.exists(f"/etc/systemd/system/{svc}.service")
        sched_installed = os.path.exists(f"/etc/systemd/system/{sched_svc}.service")

        def info():
            status_out = subprocess.run(f"systemctl is-active {svc}", shell=True, capture_output=True, text=True).stdout.strip()
            color = C_GREEN if status_out == "active" else C_RED
            return format_info_box({
                "Service": f"{C_BOLD}{svc}{C_RESET}",
                "Status": f"{color}{status_out}{C_RESET}",
                "Service File": f"{C_GREEN}Installed{C_RESET}" if svc_installed else f"{C_RED}Missing{C_RESET}",
                "Scheduler": f"{C_GREEN}Installed{C_RESET}" if sched_installed else f"{C_RED}Missing{C_RESET}"
            })
        
        svc_action_label = "Uninstall Service File" if svc_installed else "Install Service File"
        sched_action_label = "Uninstall Scheduler" if sched_installed else "Install Scheduler (Auto-Restart)"

        items = [
            ("Start", '1'),
            ("Stop", '2'),
            ("Restart", '3'),
            ("View Console Logs (journalctl)", '4'),
            ("View Scheduler Logs (Activity)", '5'),
            (svc_action_label, '6'),
            (sched_action_label, '7'),
            ("Back", 'b')
        ]

        menu = InteractiveMenu(items, title="Service Control", info_text=info, default_index=last_idx)
        c = menu.show()
        last_idx = menu.selected
        
        if c == '1': run_cmd(f"sudo systemctl start {svc}", shell=True, interactive=mgr.interactive)
        elif c == '2': run_cmd(f"sudo systemctl stop {svc}", shell=True, interactive=mgr.interactive)
        elif c == '3': run_cmd(f"sudo systemctl restart {svc}", shell=True, interactive=mgr.interactive)
        elif c == '4': 
            clear_screen()
             # Use -e to jump to end, but allow pager scrolling. 
             # No -f so we can scroll back. User can press F in less to follow.
            run_cmd(f"journalctl -u {svc} -e", shell=True, interactive=mgr.interactive)
        elif c == '5':
            view_scheduler_logs(mgr)
        elif c == '6': 
            if svc_installed: uninstall_service_file(mgr, svc)
            else: install_service_file(mgr)
        elif c == '7':
            if sched_installed: uninstall_service_file(mgr, sched_svc, is_scheduler=True)
            else: install_scheduler_service(mgr)
        elif c == 'b' or c == 'q' or c is None: return

def view_scheduler_logs(mgr):
    log_file = os.path.join(LOGS_DIR, f"scheduler_{mgr.current_instance}.log")
    if os.path.exists(log_file):
        run_cmd(f"less +G {log_file}", shell=True, interactive=mgr.interactive)
    else:
        print(f"\n{C_YELLOW}No scheduler logs found yet for this instance.{C_RESET}")
        mgr.wait_input()

def uninstall_service_file(mgr, service_name, is_scheduler=False):
    print_header("Uninstall Service")
    print(f"Service: {C_BOLD}{service_name}{C_RESET}")
    
    if is_scheduler:
         print(f"{C_YELLOW}This will disable the auto-restart scheduler.{C_RESET}")
    else:
         print(f"{C_RED}WARNING: This will remove the main server service file!{C_RESET}")

    yn_raw = safe_input(f"\nAre you sure you want to uninstall {service_name}? (y/N): ")
    yn = yn_raw.lower() if yn_raw else ""
    if yn == 'y':
        run_cmd(f"sudo systemctl stop {service_name}", shell=True, interactive=mgr.interactive)
        run_cmd(f"sudo systemctl disable {service_name}", shell=True, interactive=mgr.interactive)
        run_cmd(f"sudo rm /etc/systemd/system/{service_name}.service", shell=True, interactive=mgr.interactive)
        run_cmd("sudo systemctl daemon-reload", shell=True, interactive=mgr.interactive)
        print(f"{service_name} uninstalled.")
        mgr.wait_input()

def install_service_file(mgr):
    if mgr.interactive: print_header("Install Service")
    user = os.environ.get("USER", "root")
    install_dir = mgr.config["install_dir"]
    svc_name = mgr.config["service_name"]
    
    content = f"""[Unit]
Description=Project Zomboid Server ({svc_name})
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={install_dir}
ExecStart={install_dir}/start-server-steam.sh -adminpassword password -servername {mgr.config['server_name']} -cachedir={install_dir}/Zomboid
Restart=always

[Install]
WantedBy=multi-user.target
"""
    tmp_path = "/tmp/pzserver.service"
    with open(tmp_path, 'w') as f:
        f.write(content)
    
    print("Generated service file.")
    print("Installing to /etc/systemd/system/ (requires sudo)...")
    run_cmd(f"sudo mv {tmp_path} /etc/systemd/system/{svc_name}.service", shell=True, interactive=mgr.interactive)
    run_cmd("sudo systemctl daemon-reload", shell=True, interactive=mgr.interactive)
    print(f"Service {svc_name} installed.")
    mgr.wait_input("Press Enter...")

def install_scheduler_service(mgr):
    if mgr.interactive: print_header("Install Scheduler")
    user = os.environ.get("USER", "root")
    svc_name = mgr.config["service_name"] + "-scheduler"
    # Self path - tricky because now we are a package.
    # We should assume pz_manager.py wrapper is the entry.
    # Or use sys.argv[0] assuming it invoked the wrapper
    self_path = os.path.abspath(sys.argv[0])
    
    content = f"""[Unit]
Description=PZ Scheduler ({svc_name})
After=network.target

[Service]
Type=simple
User={user}
ExecStart=/usr/bin/python3 {self_path} --scheduler --instance {mgr.current_instance}
Restart=always

[Install]
WantedBy=multi-user.target
"""
    tmp_path = "/tmp/pzscheduler.service"
    with open(tmp_path, 'w') as f:
        f.write(content)

    print("Installing Scheduler Service...")
    run_cmd(f"sudo mv {tmp_path} /etc/systemd/system/{svc_name}.service", shell=True, interactive=mgr.interactive)
    run_cmd("sudo systemctl daemon-reload", shell=True, interactive=mgr.interactive)
    run_cmd(f"sudo systemctl enable {svc_name}", shell=True, interactive=mgr.interactive)
    run_cmd(f"sudo systemctl start {svc_name}", shell=True, interactive=mgr.interactive)
    print(f"Scheduler {svc_name} installed and started.")
    mgr.wait_input("Press Enter...")
