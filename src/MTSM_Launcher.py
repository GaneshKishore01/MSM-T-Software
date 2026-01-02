import tkinter as tk
from tkinter import ttk, messagebox
tk._default_root = None
import os
import sys
import subprocess


def get_shared_dir():
    appdata = os.getenv("APPDATA")  # C:\Users\<you>\AppData\Roaming
    shared = os.path.join(appdata, "MTSM")  # your suite folder
    os.makedirs(shared, exist_ok=True)
    return shared

def get_assets_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets")

def launch_script(script_filename):
    try:
        assets = get_assets_dir()
        exe_path = os.path.join(assets, script_filename + ".exe")
        subprocess.Popen([exe_path])
    except Exception as e:
        messagebox.showerror("Error", f"Could not launch {script_filename}:\n{e}")

#GUI Functions
def launch_monitor_popup():
    popup = tk.Toplevel(root)
    popup.title("Choose Monitoring Mode")
    popup.geometry("320x200")
    popup.transient(root)
    popup.grab_set()

    tk.Label(popup, text="🔍 Choose Monitoring Option:", font=("Arial", 12, "bold")).pack(pady=10)

    tk.Button(popup, text="🧲  Monitor from Magnet", width=30, command=lambda: [popup.destroy(), monitor_ips_from_magnet()]).pack(pady=5)
    tk.Button(popup, text="🌐  Search for Torrents", width=30, command=lambda: [popup.destroy(), launch_jackett_script()]).pack(pady=5)
    tk.Button(popup, text="📡  Host & Track", width=30,
          command=lambda: [popup.destroy(), launch_script("host_and_track")]).pack(pady=5)

def launch_jackett_script():
    launch_script("Torrent_Page_Url_JACKET")

def monitor_ips_from_magnet():
    launch_script("Ip_Tracker_magnet")

# === GUI Layout ===
root = tk.Tk()
root.title("📡 Magnet Swarm Monitor")
root.geometry("360x500")
root.protocol("WM_DELETE_WINDOW", root.destroy)
title = tk.Label(root, text="📡 Monitor and Track Swarms", font=("Arial", 18, "bold"))
title.pack(pady=10)

control_frame = tk.Frame(root)
control_frame.pack(pady=5)

tk.Button(control_frame, text="🎬 Start Monitoring", command=launch_monitor_popup, width=20).grid(row=0, column=0, padx=5)

#LOGO
from PIL import Image, ImageTk
def asset_path(filename):
    return os.path.join(get_shared_dir(), filename)

img_path = asset_path("GK_productions_logo.png")
original_img = Image.open(img_path)
resized_img = original_img.resize((350, 350))   
logo_img = ImageTk.PhotoImage(resized_img)
logo_label = tk.Label(root, image=logo_img, bg="white")
logo_label.image = logo_img    
logo_label.pack(expand=True)
bottom_frame = tk.Frame(root)
bottom_frame.pack(fill="x", padx=10, pady=(0, 10), anchor="se")

def show_settings():
    import json
    settings_path = os.path.join(get_shared_dir(), 'settings.json')

    def load_settings():
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                return json.load(f)
        return {}

    def save_settings_to_file(data):
        with open(settings_path, 'w') as f:
            json.dump(data, f, indent=4)

    saved = load_settings()
    settings_win = tk.Toplevel(root)
    settings_win.title("🛠 Settings")
    settings_win.geometry("400x300")
    settings_win.transient(root)
    settings_win.grab_set()
    notebook = ttk.Notebook(settings_win)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

#TAB 1: qBittorrent Settings
    qb_frame = tk.Frame(notebook)
    notebook.add(qb_frame, text="qBittorrent")
    entry_widgets = {}   

    entries = [
        ("Username:", "username", ""),
        ("Password:", "password", "", True),
        ("Host:", "host", "http://localhost"),
        ("WebUI Port:", "port", "8080"),
        ("Tracker URL:", "tracker", "udp://tracker.openbittorrent.com:80")
    ]

    for i, (label, key, default, *secure) in enumerate(entries):
        tk.Label(qb_frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=5)
        show = "*" if secure else None
        entry = tk.Entry(qb_frame, width=30, show=show)
        entry.insert(0, saved.get(key, default))
        entry.grid(row=i, column=1, padx=5, pady=5)
        entry_widgets[key] = entry
  
    tk.Label(
        qb_frame,
        text="🛈 To add multiple trackers, separate them with commas",
        fg="gray"
        ).grid(row=len(entries), column=0, columnspan=2, sticky="w", padx=5, pady=(0,0))
    tk.Label(
        qb_frame,
        text="🛈 Configure qBittorrent to the appropriate port",
        fg="gray"
        ).grid(row=len(entries)+1, column=0, columnspan=2, sticky="w", padx=5, pady=(0,0))


    def save_qbittorrent_settings():
        for _, key, *_ in entries:
            saved[key] = entry_widgets[key].get()
        save_settings_to_file(saved)
        messagebox.showinfo("Saved", "qBittorrent settings saved successfully!")


    tk.Button(qb_frame, text="💾 Save", command=save_qbittorrent_settings).grid(row=len(entries)+1, column=1, pady=5, sticky="e")

#TAB 2: Jackett Settings
    jackett_frame = tk.Frame(notebook)
    notebook.add(jackett_frame, text="Jackett")

    tk.Label(jackett_frame, text="Jackett API Key:").grid(row=0, column=0, sticky="w", padx=10, pady=(15, 5))
    jackett_key_var = tk.StringVar(value=saved.get("jackett_api_key", ""))
    tk.Entry(jackett_frame, textvariable=jackett_key_var, width=40).grid(row=0, column=1, padx=10, pady=(15, 5))

    tk.Label(jackett_frame, text="Host:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    jackett_host_var = tk.StringVar(value=saved.get("jackett_host", "http://localhost"))
    tk.Entry(jackett_frame, textvariable=jackett_host_var, width=40).grid(row=1, column=1, padx=10)

    tk.Label(jackett_frame, text="WebUI Port:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
    jackett_port_var = tk.StringVar(value=saved.get("jackett_port", "9117"))
    tk.Entry(jackett_frame, textvariable=jackett_port_var, width=40).grid(row=2, column=1, padx=10)  
    tk.Label(
        jackett_frame,
        text="🛈 Configure Jackett to the appropriate port",
        fg="gray"
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(0,5))


    def save_jackett_settings():
        saved.update({
            "jackett_api_key": jackett_key_var.get(),
            "jackett_host": jackett_host_var.get(),
            "jackett_port": jackett_port_var.get()
        })
        save_settings_to_file(saved)
        messagebox.showinfo("Saved", "Jackett settings saved!")

    tk.Button(jackett_frame, text="💾 Save", command=save_jackett_settings).grid(row=3, column=1, sticky="e", pady=5)

def show_about():
    messagebox.showinfo("ℹ️ About", "📡 Magnet & Torrent Swarm Monitor\nVersion: 1.3.1\nAuthor: Ganesh Kishore\n License: PolyForm Noncommercial License 1.0.0\n \n Capable of tracking peer swarms from magnet links,\n searching for magnets via Jackett,\n and monitoring peers by hosting your own files.")

#Bottom Right Buttons
settings_button = tk.Button(bottom_frame, text="🛠 Settings", width=12, command=show_settings)
settings_button.pack(side="right", padx=(0, 10))

about_button = tk.Button(bottom_frame, text="ℹ️ About", width=8, command=show_about)
about_button.pack(side="right", padx=(0, 10))

root.mainloop()