import os
import subprocess
import urllib.request
import re
from .const import *
from .utils import print_header, InteractiveMenu, SelectionMenu, ReorderMenu, get_key, clear_screen, safe_input
import itertools

class InternalModManager:
    def __init__(self, install_dir, steamcmd_dir, server_name="servertest"):
        self.install_dir = install_dir
        self.steamcmd_dir = steamcmd_dir
        self.config_file = os.path.join(install_dir, f"Zomboid/Server/{server_name}.ini")
        self.workshop_items = []
        self.mods = []
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
        if wid in self.title_cache:
            return self.title_cache[wid]
        try:
            print(f"Fetching info for {wid}...", end='\r', flush=True)
            url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={wid}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                html = response.read().decode('utf-8')
                match = re.search(r'<div class="workshopItemTitle">(.+?)</div>', html)
                if match:
                    title = match.group(1).strip()
                    self.title_cache[wid] = title
                    return title
        except Exception:
            pass
        return "Unknown Title"

    def run(self):
        if not self.load(): return
        last_index = 0
        
        while True:
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
            items_display.append(f"{C_BOLD}Add Workshop Item{C_RESET}")
            items_display.append(f"{C_BOLD}Global Mod Load Order{C_RESET}")
            items_display.append(f"{C_YELLOW}--- Active Workshop Items ---{C_RESET}")
            
            start_items_idx = 3
            for i, wid in enumerate(self.workshop_items):
                title = self.get_workshop_title(wid)
                items_display.append(f"{wid} ({title})")
                
            back_idx = len(items_display)
            items_display.append(f"{C_BOLD}Back{C_RESET}")
            
            # Render Loop
            clear_screen()
            print_header("Mod Manager")
            
            for idx, label in enumerate(items_display):
                if idx == 2: # Separator
                    print(f"  {label}")
                elif idx == last_index:
                    print(f"{C_GREEN}> {label}{C_RESET}")
                else:
                    print(f"  {label}")
            
            c = get_key()
            
            if c == '\x1b[A': # Up
                last_index = (last_index - 1) % len(items_display)
                if last_index == 2: last_index = 1 # Skip separator
            elif c == '\x1b[B': # Down
                last_index = (last_index + 1) % len(items_display)
                if last_index == 2: last_index = 3 # Skip separator
            elif c == '\r': # Enter
                if last_index == 0: # Add
                    wid = safe_input("\nWorkshop ID: ")
                    if wid:
                        wid = wid.strip()
                        if wid not in self.workshop_items:
                            self.workshop_items.append(wid)
                            self.save()
                            yn = safe_input("Download now? (y/n) ")
                            if (yn or '').lower() == 'y':
                                self.download(wid)
                elif last_index == 1: # Global Order
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
                elif last_index == back_idx: # Back
                    self.save()
                    return
                elif last_index >= start_items_idx: # Workshop Item
                    curr_item_idx = last_index - start_items_idx
                    wid = self.workshop_items[curr_item_idx]
                    
                    # Submenu for item
                    sub_items = [
                        ("Manage Mods", 'm'),
                        ("Remove Item", 'r'),
                        ("Back", 'b')
                    ]
                    sel = InteractiveMenu(sub_items, title=f"Item {wid}").show()
                    
                    if sel == 'm':
                        self.menu_item(wid)
                    elif sel == 'r':
                        yn = safe_input(f"Remove {wid}? (y/n) ")
                        if (yn or '').lower() == 'y':
                            self.workshop_items.pop(curr_item_idx)
                            self.save()
                            # Correction for cursor if we removed last item
                            if last_index >= start_items_idx + len(self.workshop_items):
                                last_index -= 1
            elif c == 'q' or c == 'b': # Quit/Back
                self.save()
                return

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
