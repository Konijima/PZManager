import os
import re
from .mod_manager import InternalModManager
from .steam_integration import SteamIntegration

class ModUpdateChecker:
    def __init__(self, mgr):
        self.mgr = mgr
        self.install_dir = mgr.config['install_dir']
        # Location of appworkshop_108600.acf
        self.acf_path = os.path.join(self.install_dir, "steamapps", "workshop", "appworkshop_108600.acf")
        self.steam_int = SteamIntegration()

    def get_installed_workshop_ids(self):
        # Use InternalModManager to parse .ini
        mm = InternalModManager(self.mgr.config['install_dir'], self.mgr.config['steamcmd_dir'], self.mgr.config['server_name'])
        if mm.load():
            return mm.workshop_items
        return []

    def parse_acf(self):
        """ Parses the ACF file to get local timestamp for each mod. """
        if not os.path.exists(self.acf_path):
            return {}
        
        local_timestamps = {}
        
        try:
            with open(self.acf_path, 'r', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            current_id = None
            in_installed = False
            
            for line in lines:
                clean = line.strip()
                if not clean: continue
                
                # Detect start of installed block
                if '"WorkshopItemsInstalled"' in clean:
                    in_installed = True
                    continue
                
                # If we are in the block
                if in_installed:
                    m_id = re.match(r'^"(\d+)"$', clean)
                    if m_id:
                        current_id = m_id.group(1)
                        continue
                        
                    m_time = re.match(r'^"timeupdated"\s+"(\d+)"', clean)
                    if m_time and current_id:
                        local_timestamps[current_id] = int(m_time.group(1))
                        # We don't reset current_id because other keys might follow
                        continue
                        
        except Exception as e:
            print(f"Error parsing ACF: {e}")
            
        return local_timestamps

    def check(self):
        active_ids = self.get_installed_workshop_ids()
        if not active_ids: return False, []
        
        local_times = self.parse_acf()
        if not local_times:
            # Maybe file missing (first run), assume no updates to avoid loop
            return False, []
            
        # Get fresh remote info
        remote_data = self.steam_int.get_item_details(active_ids, force_refresh=True)
        if not remote_data:
             return False, []
        
        updates = []
        
        for wid in active_ids:
            wid = str(wid)
            l_time = local_times.get(wid, 0)
            
            # remote_data[wid] is a dict {title, time_updated, dependencies...}
            r_info = remote_data.get(wid)
            if not r_info: continue
            
            r_time = r_info.get("time_updated", 0)
            
            # Debug
            # print(f"Mod {wid}: Local {l_time}, Remote {r_time}")
            
            if r_time > l_time:
                updates.append(wid)
                
        return (len(updates) > 0), updates

