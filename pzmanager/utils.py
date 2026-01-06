import os
import sys
import subprocess
import tty
import termios
import select
from .const import *

def get_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        # Use os.read instead of sys.stdin.read to avoid buffering issues with select()
        ch_bytes = os.read(fd, 1)
        ch = ch_bytes.decode(errors='ignore')
        
        if ch == '\x03': # Ctrl+C
            return 'q'
        if ch == '\x1b':
            # Check if there are further characters (ANSI sequence) for arrow keys
            dr, _, _ = select.select([fd], [], [], 0.05)
            if dr:
                # Sequence detected
                seq_bytes = os.read(fd, 2)
                ch += seq_bytes.decode(errors='ignore')
            else:
                # Single Escape press
                return 'b'
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

class InteractiveMenu:
    def __init__(self, items, title=None, info_text=None, default_index=0):
        self.items = items
        self.title = title
        self.info_text = info_text
        self.selected = default_index
    
    def show(self):
        while True:
            clear_screen()
            if self.title:
                print(f"{C_BLUE}{C_BOLD}=== {self.title} ==={C_RESET}")
                print(f"{C_CYAN}Project Zomboid Server Manager (Python Edition){C_RESET}\n")
            
            if self.info_text:
                text = self.info_text() if callable(self.info_text) else self.info_text
                print(text)
                print()

            for idx, item in enumerate(self.items):
                label = item[0] if isinstance(item, tuple) else item
                if idx == self.selected:
                    print(f"{C_GREEN}> {label}{C_RESET}")
                else:
                    print(f"  {label}")

            print(f"\n{C_BOLD}Use Arrow Keys to Navigate, Enter to Select{C_RESET}")

            key = get_key()
            if key == '\x1b[A': # Up
                self.selected = (self.selected - 1) % len(self.items)
            elif key == '\x1b[B': # Down
                self.selected = (self.selected + 1) % len(self.items)
            elif key == '\r': # Enter
                val = self.items[self.selected][1] if isinstance(self.items[self.selected], tuple) else self.items[self.selected]
                return val
            elif key == 'q' or key == 'b': # Quit / Back generic
                 # Check if the key is explicitly handled in items
                 for item in self.items:
                     val = item[1] if isinstance(item, tuple) else item
                     if val == key: return key
                 return None # Return None to signal cancel/back if not explicit

class ReorderMenu:
    def __init__(self, items, title=None, info_text=None, item_renderer=None):
        self.items = items[:] # Copy
        self.title = title
        self.info_text = info_text
        self.item_renderer = item_renderer
        self.selected = 0
    
    def show(self):
        while True:
            clear_screen()
            if self.title:
                print(f"{C_BLUE}{C_BOLD}=== {self.title} ==={C_RESET}")
                print(f"{C_CYAN}Project Zomboid Server Manager (Python Edition){C_RESET}\n")
            
            if self.info_text:
                print(self.info_text + "\n")

            print(f"{C_YELLOW}Use Up/Down to Navigate, +/- to Move Item, Enter to Save, q/b to Cancel{C_RESET}\n")

            for idx, item in enumerate(self.items):
                display_text = self.item_renderer(item) if self.item_renderer else str(item)
                if idx == self.selected:
                    print(f"{C_GREEN}> {display_text}{C_RESET}")
                else:
                    print(f"  {display_text}")

            key = get_key()
            if key == '\x1b[A': # Up
                self.selected = (self.selected - 1) % len(self.items)
            elif key == '\x1b[B': # Down
                self.selected = (self.selected + 1) % len(self.items)
            elif key == '+' or key == '=': # Move Up (visually up is lower index)
                if self.selected > 0:
                    self.items[self.selected], self.items[self.selected-1] = self.items[self.selected-1], self.items[self.selected]
                    self.selected -= 1
            elif key == '-' or key == '_': # Move Down
                if self.selected < len(self.items) - 1:
                    self.items[self.selected], self.items[self.selected+1] = self.items[self.selected+1], self.items[self.selected]
                    self.selected += 1
            elif key == '\r': # Enter
                return self.items
            elif key == 'q' or key == 'b':
                return None

class SelectionMenu:
    """Helper to select one item from a list"""
    def __init__(self, items, title="Select Item"):
        self.items = items
        self.title = title
    
    def show(self):
        menu_items = []
        for i, item in enumerate(self.items):
            menu_items.append((str(item), i))
        menu_items.append(("Back", -1))
        
        menu = InteractiveMenu(menu_items, title=self.title)
        return menu.show()

def clear_screen():
    os.system('clear')

def print_header(title):
    clear_screen()
    print(f"{C_BLUE}{C_BOLD}=== {title} ==={C_RESET}")
    print(f"{C_CYAN}Project Zomboid Server Manager (Python Edition){C_RESET}\n")

def safe_input(prompt=""):
    """
    Wrapper for input() that catches KeyboardInterrupt (Ctrl+C).
    Returns the stripped input string, or None if cancelled.
    """
    try:
        return input(prompt).strip()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}^C (Cancelled){C_RESET}")
        return None

def run_cmd(cmd, shell=False, check=True, interactive=True):
    try:
        return subprocess.run(cmd, shell=shell, check=check, text=True)
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Cancelled.{C_RESET}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"{C_RED}Command failed: {e}{C_RESET}")
        if interactive:
            safe_input("Press Enter to continue...")
        else:
            sys.exit(1)
        return None

def format_info_box(items_dict):
    import re
    if isinstance(items_dict, dict):
        items_dict = list(items_dict.items())
    
    if not items_dict: return ""

    def clean_len(s):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~])')
        return len(ansi_escape.sub('', str(s)))

    max_label_len = 0
    max_val_len = 0
    for k, v in items_dict:
        max_label_len = max(max_label_len, clean_len(k))
        max_val_len = max(max_val_len, clean_len(v))
    
    box_width = max_label_len + max_val_len + 7
    border_top = "┌" + "─" * (box_width - 2) + "┐"
    border_bottom = "└" + "─" * (box_width - 2) + "┘"
    
    lines = [border_top]
    for k, v in items_dict:
        vk = clean_len(k)
        vv = clean_len(v)
        sk = " " * (max_label_len - vk)
        sv = " " * (max_val_len - vv)
        lines.append(f"│ {k}{sk} : {v}{sv} │")
    lines.append(border_bottom)
    return "\n".join(lines)

def get_existing_server_names(install_dir):
    """
    Scans the Zomboid/Server directory for .ini files to find existing servers.
    """
    server_dir = os.path.join(install_dir, "Zomboid/Server")
    found = []
    if os.path.exists(server_dir):
        for f in os.listdir(server_dir):
            if f.endswith(".ini") and not f == "servertest_SandboxVars.lua": # Basic check
                name = os.path.splitext(f)[0]
                found.append(name)
    found.sort()
    return found

