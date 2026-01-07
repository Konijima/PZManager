import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from .const import CONFIG_DIR

CACHE_FILE = os.path.join(CONFIG_DIR, "workshop_cache.json")
CACHE_DURATION = 86400 # 24 Hours

class SteamIntegration:
    def __init__(self):
        self.cache = {}
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}

    def save_cache(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=4)
        except: pass

    def get_item_details(self, workshop_ids, force_refresh=False):
        """
        Fetch details for a list of workshop IDs. 
        Returns a dict mapping ID (str) -> details (dict).
        Uses cache if valid and force_refresh is False.
        """
        now = time.time()
        results = {}
        missing_ids = []
        
        # Check cache
        for wid in workshop_ids:
            wid = str(wid)
            entry = self.cache.get(wid)
            # Entry structure in cache seems to stem from whatever _fetch_from_api returned + 'fetched_at'
            # But the original code I replaced was storing as:
            # { "fetched_at": ..., "key": "value" ... } mixed
            # Wait, let's look at how I implemented _fetch_from_api in previous turns or if it's visible.
            # In the read_file output, save_cache dumps self.cache.
            
            # Let's standardize on: top level cache dict keys are WIDs. 
            # Values are dicts containing the data + 'fetched_at' timestamp.
            
            if not force_refresh and entry and (now - entry.get('fetched_at', 0) < CACHE_DURATION):
                results[wid] = entry
            else:
                missing_ids.append(wid)
        
        # Fetch missing
        if missing_ids:
            fetched = self._fetch_from_api(missing_ids)
            for wid, data in fetched.items():
                # data is the clean dict from API
                # We add our metadata
                data['fetched_at'] = now
                self.cache[wid] = data
                results[wid] = data
            
            if fetched:
                self.save_cache()
            
        return results

    def _fetch_from_api(self, workshop_ids):
        # API Limit is usually around 100 items per request, but let's batch if needed
        # For now assume list is small enough or implement simple chunking
        chunk_size = 50
        api_results = {}
        
        for i in range(0, len(workshop_ids), chunk_size):
            chunk = workshop_ids[i:i+chunk_size]
            url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
            data = {
                "itemcount": len(chunk)
            }
            for idx, wid in enumerate(chunk):
                data[f"publishedfileids[{idx}]"] = str(wid)
                
            try:
                post_data = urllib.parse.urlencode(data).encode('utf-8')
                req = urllib.request.Request(url, data=post_data)
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200: continue
                    res_json = json.loads(response.read().decode('utf-8'))
                    
                    details = res_json.get("response", {}).get("publishedfiledetails", [])
                    for item in details:
                        if item.get("result") == 1:
                            wid = str(item.get("publishedfileid"))
                            
                            # Parse Children (Dependencies)
                            # "children": [ { "publishedfileid": "..." }, ... ]
                            dependencies = []
                            if "children" in item:
                                for child in item["children"]:
                                    dependencies.append(str(child.get("publishedfileid")))
                            
                            api_results[wid] = {
                                "title": item.get("title", "Unknown"),
                                "time_updated": item.get("time_updated", 0),
                                "dependencies": dependencies
                            }
            except Exception as e:
                print(f"Steam API Error: {e}")
                
        return api_results

    def resolve_dependencies(self, workshop_ids):
        """
        Recursively finds all dependencies for the given list of workshop IDs.
        Returns a set of all required IDs (including the original ones).
        """
        resolved = set(str(x) for x in workshop_ids)
        to_check = list(resolved)
        
        while to_check:
            current_batch = to_check[:]
            to_check = []
            
            # Get details for this batch
            details = self.get_item_details(current_batch)
            
            for wid, info in details.items():
                deps = info.get("dependencies", [])
                for dep in deps:
                    if dep not in resolved:
                        resolved.add(dep)
                        to_check.append(dep)
        
        return resolved

