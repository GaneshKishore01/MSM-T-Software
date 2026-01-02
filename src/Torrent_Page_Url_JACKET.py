import os
import tkinter as tk
from tkinter import messagebox
import threading
import requests
import json
import subprocess
import sys

def get_shared_dir():
    appdata = os.getenv("APPDATA")  # C:\Users\<you>\AppData\Roaming
    shared = os.path.join(appdata, "MTSM")
    os.makedirs(shared, exist_ok=True)
    return shared


def get_exe_dir():
    if getattr(sys, 'frozen', False):  # running as EXE
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)  # running as .py

def load_jackett_config():
    settings_path = os.path.join(get_shared_dir(), 'settings.json')
    if not os.path.exists(settings_path):
        return None

    with open(settings_path, 'r') as f:
        data = json.load(f)

    host = data.get("jackett_host", "http://localhost").rstrip("/")
    port = str(data.get("jackett_port", "9117")).strip()
    if not host.endswith(f":{port}"):
        if ":" in host[host.find("//") + 2:]:
            host = host.rsplit(":", 1)[0]
        host = f"{host}:{port}"

    return {
        "base_url": host,
        "api_key": data.get("jackett_api_key", "")
    }

config = load_jackett_config()
if not config:
    raise RuntimeError("⚠️ Missing or invalid settings.json for Jackett")

JACKETT_API_KEY = config["api_key"]
JACKETT_BASE_URL = config["base_url"]

JACKETT_INDEXER_ID = "all"

HEADERS = {"User-Agent": "Mozilla/5.0"}

class JackettGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🔎 Jackett Torrent Search")
        self.geometry("1080x600")

        # Search bar
        search_frame = tk.Frame(self)
        search_frame.pack(pady=10)

        tk.Label(search_frame, text="Enter keyword:").pack(side="left", padx=(10, 5))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=50)
        self.search_entry.pack(side="left", padx=5)

        tk.Label(search_frame, text="Results:").pack(side="left", padx=(15, 5))
        self.limit_var = tk.StringVar(value="100")
        self.limit_dropdown = tk.OptionMenu(search_frame, self.limit_var, "50", "100", "200", "500", "Max (999)")
        self.limit_dropdown.pack(side="left")

        tk.Button(search_frame, text="Search", command=self.start_search_thread).pack(side="left", padx=5)

        # Results box
        result_frame = tk.Frame(self)
        result_frame.pack(padx=10, fill="both", expand=True)

        self.result_listbox = tk.Listbox(result_frame, font=("Consolas", 10), width=130, height=20)
        self.result_listbox.pack(side="left", fill="both", expand=True)
        self.result_listbox.bind("<<ListboxSelect>>", self.on_result_select)

        scrollbar = tk.Scrollbar(result_frame, orient="vertical")
        scrollbar.config(command=self.result_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.result_listbox.config(yscrollcommand=scrollbar.set)

        # Details frame
        self.detail_frame = tk.LabelFrame(self, text="Torrent Details & Actions", padx=10, pady=10)
        self.detail_frame.pack(fill="x", padx=10, pady=10)

        self.detail_text = tk.Text(self.detail_frame, height=5, font=("Consolas", 10), wrap="word")
        self.detail_text.pack(fill="x")

        action_btn_frame = tk.Frame(self.detail_frame)
        action_btn_frame.pack(pady=5)

        self.swarm_btn = tk.Button(action_btn_frame, text="🔍 Monitor Swarm & Log IPs", state="disabled", command=self.launch_swarm_monitor)
        self.swarm_btn.grid(row=0, column=0, padx=10)

        self.results_data = []

    def start_search_thread(self):
        threading.Thread(target=self.search, daemon=True).start()

    def search(self):
        self.result_listbox.delete(0, tk.END)
        self.detail_text.delete(1.0, tk.END)
        self.swarm_btn.config(state="disabled")
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Input required", "Please enter a search keyword.")
            return

        limit = self.limit_var.get()
        if limit.startswith("Max"):
            limit = 999
        else:
            limit = int(limit)

        self.result_listbox.insert(tk.END, f"🔍 Searching for: {query}...")

        url = f"{JACKETT_BASE_URL}/api/v2.0/indexers/all/results?apikey={JACKETT_API_KEY}&query={query}"

        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            results = data.get("Results", [])

            results = [r for r in results if r.get("Seeders", 0) > 0]
            results.sort(key=lambda r: r.get("Seeders", 0), reverse=True)
            results = results[:limit]

            self.results_data = results
            self.result_listbox.delete(0, tk.END)

            if not results:
                self.result_listbox.insert(tk.END, "❌ No results found.")
                return

            self.result_listbox.insert(tk.END, f"📋 {len(results)} result(s) found (sorted by seeders):")
            self.result_listbox.insert(tk.END, "=" * 120)
            for i, item in enumerate(results, 1):
                title = item.get("Title", "N/A")
                size = item.get("Size", 0)
                size_mb = round(size / (1024 * 1024), 2)
                seeders = item.get("Seeders", 0)
                peers = item.get("Peers", 0)
                display = f"{i:>2}. {title[:60]:<60} | {size_mb:>6} MB | 🌱 {seeders:<3} | 🧲 {peers:<3}"
                self.result_listbox.insert(tk.END, display)
        except Exception as e:
            self.result_listbox.insert(tk.END, f"❌ Error: {e}")

    def on_result_select(self, event):
        selection = event.widget.curselection()
        if not selection:
            return

        index = selection[0] - 2
        if index < 0 or index >= len(self.results_data):
            return

        item = self.results_data[index]
        title = item.get("Title", "N/A")
        magnet = item.get("MagnetUri", "N/A")
        self.current_magnet_link = magnet

        detail = f"Title: {title}\n\nMagnet Link:\n{magnet}"
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, detail)

        self.swarm_btn.config(state="normal")

    def launch_swarm_monitor(self):
        try:
            base = get_exe_dir()
            script_path = os.path.join(base, "Ip_Tracker_magnet.py")
            magnet_link = getattr(self, 'current_magnet_link', None)
            if not magnet_link or magnet_link == "N/A":
                messagebox.showwarning("No Magnet Link", "Please select a torrent first.")
                return
            subprocess.Popen([sys.executable, script_path, magnet_link])
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to start swarm monitor:\n{e}")

if __name__ == "__main__":
    app = JackettGUI()
    app.mainloop()
