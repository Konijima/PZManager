#!/usr/bin/env python3
import sys
import os
import argparse

# Ensure we can import the package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pzmanager.core import PZManager
from pzmanager.utils import run_cmd

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PZ Manager")
    parser.add_argument("action", nargs="?", default=None, help="Action to perform (start, stop, restart, status, logs, install, backup)")
    parser.add_argument("--instance", default=None, help="Target specific server instance")
    parser.add_argument("--scheduler", action="store_true", help="Run the scheduler process")
    
    args = parser.parse_args()
    
    # Determine mode
    # Legacy: if action is "--scheduler", treat as flag
    if args.action == "--scheduler":
        args.scheduler = True
        args.action = None

    is_interactive = (args.action is None and not args.scheduler)
    
    try:
        app = PZManager(interactive=is_interactive, instance_name=args.instance)
        
        if args.scheduler:
            app.run_scheduler()
        elif args.action:
            cmd = args.action
            svc = app.config.get('service_name', 'pzserver')
            
            if cmd == "start": run_cmd(f"sudo systemctl start {svc}", shell=True, interactive=False)
            elif cmd == "stop": run_cmd(f"sudo systemctl stop {svc}", shell=True, interactive=False)
            elif cmd == "restart": run_cmd(f"sudo systemctl restart {svc}", shell=True, interactive=False)
            elif cmd == "status": run_cmd(f"sudo systemctl status {svc}", shell=True, interactive=False)
            elif cmd == "logs": run_cmd(f"journalctl -u {svc} -f", shell=True, interactive=False)
            elif cmd == "install": app.install_server()
            elif cmd == "backup": app.submenu_backup()
            else:
                print(f"Unknown command: {cmd}")
        else:
            app.main_menu()
            
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
