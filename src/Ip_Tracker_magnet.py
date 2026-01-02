import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import qbittorrentapi
import requests
import sys

def get_shared_dir():
    appdata = os.getenv("APPDATA")  # C:\Users\<you>\AppData\Roaming
    shared = os.path.join(appdata, "MTSM")
    os.makedirs(shared, exist_ok=True)
    return shared

#File Paths
#last magnet is for refresh feature
base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(__file__)
SETTINGS_PATH = os.path.join(get_shared_dir(), 'settings.json')
MAGNET_CACHE_PATH = os.path.join(get_shared_dir(), 'last_magnet.txt')
DOWNLOAD_LIMIT_KBPS = 100

def load_qbittorrent_config():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'r') as f:
            data = json.load(f)
            return {
                "host": data.get("host", "http://localhost").rstrip('/'),
                "port": str(data.get("port", "8080")),
                "username": data.get("username", "admin"),
                "password": data.get("password", "adminadmin")
            }
    else:
        return None

class MagnetIPTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Magnet IP Tracker with ipwho.is API")
        self.root.geometry("700x500")

        # Magnet input
        ttk.Label(root, text="Enter Magnet Link:").pack(pady=(10, 0))
        self.magnet_var = tk.StringVar()
        self.magnet_entry = ttk.Entry(root, textvariable=self.magnet_var, width=90)
        self.magnet_entry.pack(pady=5)

        # Max Peers slider
        ttk.Label(root, text="Max Peers to Track:").pack()
        peer_frame = ttk.Frame(root)
        peer_frame.pack(pady=(0, 10))

        self.max_peers_var = tk.IntVar(value=10)
        self.max_peers_slider = ttk.Scale(peer_frame, from_=1, to=200, orient="horizontal", variable=self.max_peers_var, length=400)
        self.max_peers_slider.pack(side="left", padx=(0, 10))

        self.peer_count_label = ttk.Label(peer_frame, text="10")
        self.peer_count_label.pack(side="left")

        def update_peer_label(val):
            self.peer_count_label.config(text=str(int(float(val))))
        self.max_peers_slider.config(command=update_peer_label)
        self.infinite_var = tk.BooleanVar(value=False)
        self.infinite_check = ttk.Checkbutton(root, text="∞ Infinite Peers", variable=self.infinite_var)
        self.infinite_check.pack()
        ttk.Label(root, text="Refresh Interval:").pack(pady=(5, 0))
        self.refresh_var = tk.StringVar(value="manual")
        self.refresh_menu = ttk.Combobox(root, textvariable=self.refresh_var, state="readonly", values=["manual", "5s", "10s", "30s", "1m"])
        self.refresh_menu.pack()
        self.start_btn = ttk.Button(root, text="Add & Track Peers", command=self.start_process)
        self.start_btn.pack(pady=5)
        self.refresh_btn = ttk.Button(root, text="🔄 Refresh IP Info", command=self.manual_refresh)
        self.refresh_btn.pack(pady=(0, 10))
        self.status_box = scrolledtext.ScrolledText(root, height=20, width=90, font=("Consolas", 10))
        self.status_box.pack(pady=10)
        self.client = None
        self.torrent_hash = None

    def log(self, msg):
        self.status_box.insert(tk.END, msg + "\n")
        self.status_box.see(tk.END)
        self.root.update()

    def manual_refresh(self):
        if os.path.exists(MAGNET_CACHE_PATH):
            with open(MAGNET_CACHE_PATH, 'r') as f:
                magnet = f.read().strip()
            if magnet:
                self.magnet_var.set(magnet)
                threading.Thread(target=lambda: self.run(refresh_only=False), daemon=True).start()
            else:
                self.log("⚠️ No cached magnet to refresh.")
        else:
            self.log("⚠️ No cached magnet file found.")

    def start_auto_refresh(self):
        def refresher():
            while True:
                interval = self.refresh_var.get()
                if interval == "manual":
                    break
                delay_map = {"5s": 5, "10s": 10, "30s": 30, "1m": 60}
                delay = delay_map.get(interval, 0)
                time.sleep(delay)
                self.log(f"🔁 Auto-refresh every {interval}...")
                self.manual_refresh()
        threading.Thread(target=refresher, daemon=True).start()

    def setup_qbittorrent_client(self):
        config = load_qbittorrent_config()
        if not config:
            messagebox.showerror("Config Missing", "settings.json not found or invalid!")
            self.log("❌ settings.json missing or invalid!")
            return False

        full_host = config["host"]
        if not full_host.endswith(f":{config['port']}"):
            if ":" in full_host[full_host.find("//") + 2:]:
                full_host = full_host.rsplit(":", 1)[0]
            full_host = f"{full_host}:{config['port']}"

        self.log(f"🔗 Logging into qBittorrent Web UI at {full_host} ...")
        try:
            self.client = qbittorrentapi.Client(
                host=full_host,
                username=config["username"],
                password=config["password"]
            )
            self.client.auth_log_in()
            self.log("✅ Logged in successfully.")
        except Exception as e:
            messagebox.showerror("Login Error", f"Failed to login to qBittorrent:\n{e}")
            self.log(f"❌ Login failed: {e}")
            return False
        return True

    def add_torrent(self, magnet):
        self.log(f"➕ Adding torrent to qBittorrent...")
        try:
            self.client.torrents_add(urls=magnet)
            self.log("⏳ Waiting for metadata...")
            for _ in range(30):
                time.sleep(1)
                torrents = self.client.torrents_info()
                for t in torrents:
                    if t.magnet_uri == magnet or t.hash.lower() in magnet.lower():
                        self.torrent_hash = t.hash
                        self.client.torrents_set_download_limit(
                            limit=DOWNLOAD_LIMIT_KBPS * 1024,
                            torrent_hashes=self.torrent_hash
                        )
                        self.log(f"✅ Torrent added. Hash: {self.torrent_hash}")
                        return True
            self.log("❌ Timeout: Failed to get torrent metadata.")
        except Exception as e:
            self.log(f"❌ Error adding torrent: {e}")
        return False

    def fetch_peer_ips(self):
        self.log("🔍 Fetching peer list...")
        peers = []
        try:
            max_peers = 999 if self.infinite_var.get() else int(self.max_peers_var.get())
            peers_response = self.client.sync.torrent_peers(self.torrent_hash)
            peer_items = list(peers_response.get('peers', {}).items())
            for i, (ip, info) in enumerate(peer_items[:max_peers]):
                pure_ip = ip.split(":")[0]
                peers.append(pure_ip)
                self.log(f"Peer {i+1}: IP={ip}, Port={info.get('port', 'N/A')}")
        except Exception as e:
            self.log(f"❌ Error fetching peers: {e}")
        return peers

    def query_ipwhois(self, ip):
        self.log(f"🌐 Querying ipwho.is for {ip} ...")
        try:
            resp = requests.get(f"http://ipwho.is/{ip}", timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    self.log(f"❌ Invalid JSON from ipwho.is for IP: {ip} — raw: {resp.text[:100]!r}")
                    return

                if data.get("success"):
                    sec = data.get("security", {})
                    details = (
                        f"IP: {ip}\n"
                        f"ASN: {data.get('asn', 'N/A')}\n"
                        f"ISP: {data.get('isp', 'N/A')}\n"
                        f"Country: {data.get('country', 'N/A')}\n"
                        f"Hostname: {data.get('hostname', 'N/A')}\n"
                        f"City: {data.get('city', 'N/A')}\n"
                        f"Region: {data.get('region', 'N/A')}\n"
                        f"VPN: {sec.get('vpn', 'N/A')}\n"
                        f"Proxy: {sec.get('proxy', 'N/A')}\n"
                        f"Anonymous: {sec.get('anonymous', 'N/A')}\n"
                        f"TOR: {sec.get('tor', 'N/A')}\n"
                        f"Hosting: {sec.get('hosting', 'N/A')}\n"
                        "-----------------------------"
                    )
                    self.log(details)
                else:
                    self.log(f"❌ ipwho.is query unsuccessful for IP: {ip}")
            else:
                self.log(f"❌ HTTP error from ipwho.is: {resp.status_code} for IP: {ip}")
        except Exception as e:
            self.log(f"❌ Exception querying ipwho.is for {ip}: {e}")

    def delete_torrent(self):
        self.log("🗑️ Deleting torrent and files from qBittorrent...")
        try:
            self.client.torrents_delete(delete_files=True, torrent_hashes=self.torrent_hash)
            self.log("✅ Torrent and files deleted successfully.")
        except Exception as e:
            self.log(f"❌ Error deleting torrent: {e}")

    def run(self, refresh_only=False):
        magnet = self.magnet_var.get().strip()
        if not magnet.startswith("magnet:?"):
            messagebox.showerror("Invalid Input", "Please enter a valid magnet link.")
            return

        if not self.setup_qbittorrent_client():
            return

        if not refresh_only:
            with open(MAGNET_CACHE_PATH, 'w') as f:
                f.write(magnet)

        if not self.add_torrent(magnet):
            return

        peers = self.fetch_peer_ips()
        if not peers:
            self.log("⚠️ No peers found to query.")
        else:
            for ip in peers:
                self.query_ipwhois(ip)

        if self.refresh_var.get() != "manual":
            self.start_auto_refresh()

        self.delete_torrent()
        self.log("✅ All tasks complete.")

    def start_process(self):
        threading.Thread(target=self.run, daemon=True).start()

def run_gui(parent=None):
    win = tk.Toplevel(parent)
    app = MagnetIPTrackerApp(win)
    return app

if __name__ == "__main__":
    root = tk.Tk()
    app = MagnetIPTrackerApp(root)
    root.mainloop()

