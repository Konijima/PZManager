import os
import subprocess
import re
import time
from .const import *
from .utils import print_header, InteractiveMenu, SelectionMenu, ReorderMenu, get_key, clear_screen, safe_input
from .steam_integration import SteamIntegration
import itertools

class InternalModManager:
    def __init__(self, install_dir, steamcmd_dir, server_name="servertest"):
        self.install_dir = install_dir
        self.steamcmd_dir = steamcmd_dir
        self.config_file = os.path.join(install_dir, f"Zomboid/Server/{server_name}.ini")
        self.workshop_items = []
        self.mods = []
        self.steam_int = SteamIntegration()
        self.title_cache = {}

    def load(self):
        if not os.path.exists(self.config_file):
            print("Config file not found. Install server first.")
            return False
        with open(self.config_file, 'r') as f:
            self.raw_lines = f.readlines()
        for line in self.raw_lines:
            if line.strip().startswith("WorkshopItems="):
                parts = line.split("=",1)[1].strip().split(";")
                self.workshop_items = [x for x in parts if x]
            if line.strip().startswith("Mods="):
                parts = line.split("=",1)[1].strip().split(";")
                self.mods = [x for x in parts if x]
        return True

    def save(self):
        w_str = "WorkshopItems=" + ";".join(self.workshop_items)
        m_str = "Mods=" + ";".join(self.mods)
        new_lines = []
        w_done = m_done = False
        for line in self.raw_lines:
            if line.strip().startswith("WorkshopItems="):
                new_lines.append(w_str + "\n")
                w_done = True
            elif line.strip().startswith("Mods="):
                new_lines.append(m_str + "\n")
                m_done = True
            else:
                new_lines.append(line)
        if not w_done: new_lines.append(w_str + "\n")
        if not m_done: new_lines.append(m_str + "\n")
        with open(self.config_file, 'w') as f:
            f.writelines(new_lines)

    def download(self, wid):
        print(f"Downloading Workshop ID {wid}...")
        steam = os.path.join(self.steamcmd_dir, "steamcmd.sh")
        cmd = [steam, "+force_install_dir", self.install_dir, "+login", "anonymous", "+workshop_download_item", "108600", str(wid), "+quit"]
        subprocess.run(cmd)

    def get_mods_for_item(self, wid):
        path = os.path.join(self.install_dir, "steamapps/workshop/content/108600", str(wid), "mods")
        found = []
        if os.path.exists(path):
            for d in os.listdir(path):
                found.append(d)
        return found

    def get_workshop_title(self, wid):
        # Use SteamIntegration to get title
        wid = str(wid)
        details = self.steam_int.get_item_details([wid])
        info = details.get(wid)
        if info:
            return info.get("title", f"Unknown ({wid})")
        return f"Unknown ({wid})"

    def resolve_and_add_dependencies(self, wid):
        print("Resolving dependencies (this may take a few seconds)...")
        resolved = self.steam_int.resolve_dependencies([wid])
        
        count = 0
        for dep in resolved:
            if dep not in self.workshop_items:
                self.workshop_items.append(dep)
                count += 1
        return count

    def sort_mods_by_dependency(self):
        """
        Sorts self.mods based on require= in mod.info
        """
        # 1. Build Dependency Graph
        # Map: ModID -> { set of required ModIDs }
        adj = {}
        all_available_mods = {} # Map ModID -> (WorkshopID, Path)
        
        # Scan all installed workshop items to find ModIDs
        for wid in self.workshop_items:
            path = os.path.join(self.install_dir, "steamapps/workshop/content/108600", str(wid), "mods")
            if os.path.exists(path):
                for d in os.listdir(path):
                    mod_info_path = os.path.join(path, d, "mod.info")
                    if os.path.exists(mod_info_path):
                        # Parse
                        m_id = d # Default folder name
                        requires = []
                        try:
                            with open(mod_info_path, "r", encoding="utf-8", errors="ignore") as f:
                                for line in f:
                                    if line.startswith("id="):
                                        m_id = line.split("=", 1)[1].strip()
                                    elif line.startswith("require="):
                                        # require=mod1,mod2
                                        req_str = line.split("=", 1)[1].strip()
                                        requires = [r.strip() for r in req_str.split(",") if r.strip()]
                        except: pass
                        
                        all_available_mods[m_id] = wid
                        adj[m_id] = set(requires)

        # 2. Build subgraph of active mods only
        active = set(self.mods)
        # Verify all active mods are found?
        
        # 3. Topological Sort
        # Provide order
        ordered = []
        visited = set()
        temp = set()

        def visit(node):
            if node in temp:
                # Cycle detected
                return
            if node in visited:
                return
            if node not in active:
                # Dependency not active? 
                # Should we auto-activate or just ignore ordering constraint for missing node?
                return 

            temp.add(node)
            
            # Visit dependencies first
            reqs = adj.get(node, set())
            for r in reqs:
                visit(r)
                
            temp.remove(node)
            visited.add(node)
            ordered.append(node)

        for m in self.mods:
             # Just strict order?
             # Note: if cycle, simple DFS might fail or infinite recursion without temp check
             visit(m)
             
        # Add any disconnected components (should be covered by loop but verify)
        # ordered contains sorted list
        # However, visit might skip nodes if 'active' check prevents it?
        # Actually visit(m) ensures we process all requested mods.
        
        # Replace
        self.mods = ordered

    def run(self):
        if not self.load(): return
        last_index = 0
        
        while True:
            # OPTIMIZATION: Batch fetch details for all items to populate cache
            # This avoids N+1 API calls during the sort loop and rendering
            self.steam_int.get_item_details(self.workshop_items)
            
            # Sort workshop items by title
            self.workshop_items.sort(key=lambda x: self.get_workshop_title(x).lower())
            
            # Build current menu items
            # Structure: 
            # 0: Add
            # 1: Global Order
            # 2: ---
            # 3..N: Workshop Items
            # N+1: Back
            
            items_display = []
            items_display.append(("Add Workshop Item", 'add', "Add a new mod by ID (checks dependencies)"))
            items_display.append(("Global Mod Load Order (Manual)", 'order', "Reorder the active mods list manually"))
            items_display.append(("Auto-Sort Load Order (Dependency Check)", 'sort', "Sort active mods based on 'require=' fields"))
            items_display.append(("Update Workshop Names (Cache)", 'cache', "Refresh titles from Steam Workshop"))
            items_display.append((f"{C_YELLOW}--- Active Workshop Items ---{C_RESET}", None, ""))
            
            for i, wid in enumerate(self.workshop_items):
                title = self.get_workshop_title(wid)
                items_display.append((f"{wid} ({title})", wid, f"Manage mods inside Workshop Item {wid}"))
            
            items_display.append(("Back", 'back', "Return to Main Menu"))
            
            menu = InteractiveMenu(items_display, title="Mod Manager", default_index=last_index)
            choice = menu.show()
            last_index = menu.selected
            
            if choice == 'back' or choice == 'q' or choice is None:
                self.save()
                return

            elif choice == 'add':
                wid = safe_input("\nWorkshop ID: ")
                if wid:
                    wid = wid.strip()
                    if wid and wid not in self.workshop_items:
                        self.workshop_items.append(wid)
                        # Check Deps
                        yn = safe_input("Check for required dependencies? (Y/n) ")
                        if (yn or 'y').lower() == 'y':
                            added = self.resolve_and_add_dependencies(wid)
                            if added > 0: print(f"Added {added} dependencies.")
                        
                        self.save()
                        yn = safe_input("Download now? (Y/n) ")
                        if (yn or 'y').lower() == 'y':
                            self.download(wid)
            
            elif choice == 'sort':
                print("Sorting mods...")
                old_mods = list(self.mods)
                self.sort_mods_by_dependency()
                
                if old_mods == self.mods:
                    print(f"{C_GREEN}Load order is already optimal.{C_RESET}")
                else:
                    print(f"{C_GREEN}Mods sorted by dependencies!{C_RESET}")
                    print(f"\n{C_YELLOW}Changes:{C_RESET}")
                    
                    # Identify moves?
                    # Simple comparison: List formatted nicely
                    # Or just show list of what changed position
                    for i, mod in enumerate(self.mods):
                        if i < len(old_mods) and old_mods[i] == mod:
                            continue
                        
                        # Find where this mod was before
                        old_idx = -1
                        if mod in old_mods: old_idx = old_mods.index(mod)
                        
                        print(f" [{i+1}] {mod} (was {old_idx+1})")
                        
                safe_input("\nPress Enter...")
                self.save()

            elif choice == 'cache':
                print("Refreshing Workshop Cache from Steam API...")
                # Force refresh calls API regardless of cache age
                self.steam_int.get_item_details(self.workshop_items, force_refresh=True)
                print("Cache updated. Titles and dependencies refreshed.")
                time.sleep(1)

            elif choice == 'order': # Global Order
                # Prepare renderer
                mod_map = {}
                wid_colors = {}
                colors = [C_CYAN, C_MAGENTA, C_YELLOW, C_BLUE, C_RED]
                cyc = itertools.cycle(colors)
                
                for wid in self.workshop_items:
                    wid_colors[wid] = next(cyc)
                    for m in self.get_mods_for_item(wid):
                        mod_map[m] = wid
                        
                def renderer(m):
                    wid = mod_map.get(m)
                    if wid:
                        c = wid_colors.get(wid, C_RESET)
                        return f"[{wid}] {c}{m}{C_RESET}"
                    return m

                reordered = ReorderMenu(self.mods, title="Global Mod Load Order", item_renderer=renderer).show()
                if reordered is not None:
                    self.mods = reordered
                    self.save()

            elif str(choice).isdigit(): # Workshop Item ID
                wid = choice
                self.menu_item(wid)


    def menu_item(self, wid):
        last_index = 0
        while True:
            available = self.get_mods_for_item(wid)
            if not available:
                print_header(f"Workshop Item {wid}")
                print("No mods found locally. (Try downloading the item)")
                yn = safe_input("Download? (y/n) ")
                if (yn or '').lower() == 'y':
                    self.download(wid)
                    continue
                else:
                    return

            menu_items = []
            for m in available:
                status = f"{C_GREEN}[ON] {C_RESET}" if m in self.mods else f"{C_RED}[OFF]{C_RESET}"
                menu_items.append((f"{status} {m}", m))
            menu_items.append(("Back", "b"))

            title = str(wid)
            if wid in self.title_cache:
                title += f" ({self.title_cache[wid]})"
            
            menu = InteractiveMenu(menu_items, title=f"Workshop Item {title}", default_index=last_index)
            val = menu.show()
            last_index = menu.selected
            
            if val == 'b' or val == 'q' or val is None:
                return
            
            # Toggle logic
            mod_name = val
            if mod_name in self.mods:
                self.mods.remove(mod_name)
            else:
                self.mods.append(mod_name)
            self.save()
