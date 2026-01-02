import qbittorrentapi
import os
import time
import hashlib
import bencodepy
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import json

def get_shared_dir():
    appdata = os.getenv("APPDATA")
    shared = os.path.join(appdata, "MTSM")
    os.makedirs(shared, exist_ok=True)
    return shared

# Load settings.json
def load_settings():
    settings_path = os.path.join(get_shared_dir(), "settings.json")


    if not os.path.exists(settings_path):
        raise RuntimeError("❌ settings.json missing — Script #2 cannot run.")

    with open(settings_path, "r") as f:
        data = json.load(f)

    # Pull qBittorrent config
    host = data.get("host", "http://localhost").rstrip("/")
    port = str(data.get("port", "8080")).strip()

    # Normalize host:port
    if not host.endswith(f":{port}"):
        if ":" in host[host.find("//") + 2:]:
            host = host.rsplit(":", 1)[0]
        host = f"{host}:{port}"

    return {
        "qb_host": host,
        "qb_username": data.get("username", "admin"),
        "qb_password": data.get("password", "adminadmin"),

        # Tracker URL for generated torrents
        "tracker": data.get("tracker", "udp://tracker.openbittorrent.com:80")
    }

# Load config once
CONFIG = load_settings()
QBITTORRENT_HOST = CONFIG["qb_host"]
QBITTORRENT_USERNAME = CONFIG["qb_username"]
QBITTORRENT_PASSWORD = CONFIG["qb_password"]
TRACKER_URL = CONFIG["tracker"]
TRACKER_LIST = [t.strip() for t in TRACKER_URL.split(",") if t.strip()]

# Log directory
base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(__file__)
SAVE_DIR = os.path.join(base, "host_logs")
os.makedirs(SAVE_DIR, exist_ok=True)

def ask_open_file():
    root = tk.Tk()
    root.withdraw()
    filename = root.tk.call('tk_getOpenFile')
    root.destroy()
    return filename


def make_torrent_file(file_path, torrent_path, announce_url=TRACKER_URL):
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    piece_length = 256 * 1024  # 256 KB

    with open(file_path, "rb") as f:
        pieces = b''
        while True:
            piece = f.read(piece_length)
            if not piece:
                break
            sha1 = hashlib.sha1(piece).digest()
            pieces += sha1

    torrent_dict = {
        b'announce': TRACKER_LIST[0].encode(),     # main tracker
        b'announce-list': [ [t.encode()] for t in TRACKER_LIST ],  # all trackers
        b'info': {
            b'name': file_name.encode(),
            b'length': file_size,
            b'piece length': piece_length,
            b'pieces': pieces
            }
        }


    encoded = bencodepy.encode(torrent_dict)
    with open(torrent_path, "wb") as f:
        f.write(encoded)

    print(f"✅ Torrent file created: {torrent_path}")


def login_qb():
    client = qbittorrentapi.Client(
        host=QBITTORRENT_HOST,
        username=QBITTORRENT_USERNAME,
        password=QBITTORRENT_PASSWORD
    )
    client.auth_log_in()
    print("✅ Logged into qBittorrent using settings.json")
    return client

def host_file_and_track_peers(file_path):
    file_name = os.path.basename(file_path)
    torrent_path = file_path + ".torrent"

    make_torrent_file(file_path, torrent_path)

    client = login_qb()
    client.torrents_add(
        torrent_files=torrent_path,
        save_path=os.path.dirname(file_path),
        is_paused=False,
        is_sequential_download=False
    )

    print(f"📡 Hosting: {file_name}")

    time.sleep(5)
    torrents = client.torrents_info()

    for t in torrents:
        if t.name == file_name:

            magnet_link = t.magnet_uri

            # ---------------------------
            # GET PEERS (SEEDERS + LEECHERS)
            # ---------------------------
            def get_peers():
                peers_raw = client.sync.torrent_peers(t.hash).get("peers", {})
                seeders = {}
                leechers = {}

                for ip, data in peers_raw.items():
                    ipport = f"{ip}:{data.get('port', 0)}"
                    progress = data.get("progress", 0)

                    if progress >= 1.0:
                        seeders[ip] = ipport
                    else:
                        leechers[ip] = ipport

                return seeders, leechers

            # ---------------------------
            # DELETE FILES
            # ---------------------------
            def delete_files():
                try: os.remove(file_path)
                except: pass
                try: os.remove(torrent_path)
                except: pass

            # ---------------------------
            # OPEN WINDOW  ← You forgot to indent this!!!
            # ---------------------------
            open_host_monitor_window(
                torrent_name=file_name,
                file_path=file_path,
                magnet_link=magnet_link,
                get_peers_callback=get_peers,
                delete_callback=delete_files
            )

            return  # VERY IMPORTANT


# ---------------------------
# HOST MONITOR WINDOW
# ---------------------------
def open_host_monitor_window(torrent_name, file_path, magnet_link, get_peers_callback, delete_callback=None):
    win = tk.Toplevel()
    win.title("📡 Hosting Monitor")
    win.geometry("900x550")
    win.resizable(False, False)

    # ===== INFO SECTION =====
    info = tk.LabelFrame(win, text="Hosted Torrent Info", padx=10, pady=10)
    info.pack(fill="x", padx=10, pady=10)

    size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    tk.Label(info, text=f"📄 File: {torrent_name}").pack(anchor="w")
    tk.Label(info, text=f"💾 Size: {size_mb} MB").pack(anchor="w")

    # Magnet row
    mf = tk.Frame(info)
    mf.pack(anchor="w", pady=4)

    tk.Label(mf, text="🧲 Magnet:").grid(row=0, column=0)
    magnet_entry = tk.Entry(mf, width=90)
    magnet_entry.insert(0, magnet_link)
    magnet_entry.grid(row=0, column=1, padx=5)

    def copy_magnet():
        win.clipboard_clear()
        win.clipboard_append(magnet_link)
        win.update()
        messagebox.showinfo("Copied!", "Magnet copied!")

    tk.Button(mf, text="Copy", command=copy_magnet).grid(row=0, column=2, padx=5)

    # ===== SEEDERS + LEECHERS TABLES =====
    tables_frame = tk.Frame(win)
    tables_frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Seeders
    seed_frame = tk.LabelFrame(tables_frame, text="SEEDERS (uploaders)", padx=10, pady=10)
    seed_frame.pack(side="left", fill="both", expand=True)

    seed_table = ttk.Treeview(seed_frame, columns=("ip",), show="headings", height=12)
    seed_table.heading("ip", text="IP:PORT")
    seed_table.column("ip", width=250)
    seed_table.pack(fill="both", expand=True)

    # Leechers
    leech_frame = tk.LabelFrame(tables_frame, text="LEECHERS (downloaders)", padx=10, pady=10)
    leech_frame.pack(side="right", fill="both", expand=True)

    leech_table = ttk.Treeview(leech_frame, columns=("ip",), show="headings", height=12)
    leech_table.heading("ip", text="IP:PORT")
    leech_table.column("ip", width=250)
    leech_table.pack(fill="both", expand=True)

    # ===== REFRESH BUTTON =====
    def refresh_tables():
        seeders, leechers = get_peers_callback()

        seed_table.delete(*seed_table.get_children())
        leech_table.delete(*leech_table.get_children())

        for ipport in seeders.values():
            seed_table.insert("", "end", values=(ipport,))
        for ipport in leechers.values():
            leech_table.insert("", "end", values=(ipport,))

    tk.Button(win, text="🔄 Refresh", command=refresh_tables).pack(pady=5)

    # Auto-refresh every 5 seconds
    def auto_refresh():
        if win.winfo_exists():
            refresh_tables()
            win.after(5000, auto_refresh)

    auto_refresh()

    # ===== DELETE OPTION =====
    delete_var = tk.BooleanVar()
    tk.Checkbutton(win, text="🗑️ Delete host file on close", variable=delete_var).pack()

    def on_close():
        if delete_var.get() and delete_callback:
            delete_callback()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)
          
    return   # VERY IMPORTANT

# ============================================
# GUI: Select File OR Create Dummy → Host+Track
# ============================================
def open_host_gui():
    root = tk.Tk()
    root.title("📡 Host & Track")
    root.geometry("420x300")
    root.resizable(False, False)

    # Title
    tk.Label(root, text="📡 Host & Track", font=("Arial", 16, "bold")).pack(pady=(10, 0))

    # Radiobutton variable
    mode = tk.StringVar(value="existing")   # default = Host existing file
    selected_file_path = tk.StringVar()

    # --- Option 1: Host an existing file ---
    frame_existing = tk.Frame(root)
    frame_existing.pack(fill="x", padx=20, pady=5)

    row = tk.Frame(frame_existing)
    row.pack(fill="x", pady=3)

    tk.Radiobutton(row, text="Host an existing file", value="existing", variable=mode).pack(side="left")

    btn_select_file = tk.Button(row, text="[ Select File ]", width=15)
    btn_select_file.pack(side="left", padx=10)
    file_path_label = tk.Label(frame_existing, textvariable=selected_file_path, fg="gray", font=("Arial", 9))
    file_path_label.pack(anchor="w", padx=25)


    def pick_file():
        fp = ask_open_file()
        if not fp:
            return
        selected_file_path.set(fp)
        
    btn_select_file.config(command=pick_file)

    frame_dummy = tk.Frame(root)
    frame_dummy.pack(fill="x", padx=20, pady=10)

    tk.Radiobutton(frame_dummy, text="Create a dummy file",
                   value="dummy", variable=mode).pack(anchor="w")

    # Dummy file settings box
    settings = tk.Frame(frame_dummy)
    settings.pack(fill="x", padx=25, pady=5)

    row_name = tk.Frame(settings)
    row_name.pack(fill="x", pady=2)
    tk.Label(row_name, text="Name:").pack(side="left")
    name_entry = tk.Entry(row_name, width=25)
    name_entry.pack(side="left", padx=10)

    tk.Label(settings, text="Size:").pack(anchor="w", pady=(5, 0))
    size_var = tk.StringVar()
    size_box = ttk.Combobox(settings, textvariable=size_var, width=22,
                            state="readonly",
                            values=["5 MB", "50 MB", "500 MB", "1 GB", "2 GB", "4 GB"])
    size_box.pack(anchor="w")
    size_box.set("500 MB")

    # --- Unified Host Button (Option B) ---
    host_btn = tk.Button(root, text="▶ Host File", width=25)
    host_btn.pack(pady=10)

    def host_action():
        # =======================
        # EXISTING FILE MODE
        # =======================
        if mode.get() == "existing":
            fp = selected_file_path.get()
            if not fp:
                messagebox.showerror("Error", "Please select a file first!")
                return
            host_file_and_track_peers(fp)
            return

        # =======================
        # DUMMY FILE MODE
        # =======================
        size_map = {
            "5 MB": 5 * 1024 * 1024,
            "50 MB": 50 * 1024 * 1024,
            "500 MB": 500 * 1024 * 1024,
            "1 GB": 1 * 1024 * 1024 * 1024,
            "2 GB": 2 * 1024 * 1024 * 1024,
            "4 GB": 4 * 1024 * 1024 * 1024
        }

        name = name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Enter a dummy file name.")
            return

        filepath = os.path.join(os.getcwd(), name)
        filesize = size_map[size_var.get()]

        try:
            with open(filepath, "wb") as f:
                f.seek(filesize - 1)
                f.write(b"\0")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create file:\n{e}")
            return

        host_file_and_track_peers(filepath)

    host_btn.config(command=host_action)

    # Enable/Disable dummy fields dynamically
    def update_mode(*args):
        is_dummy = (mode.get() == "dummy")

        # existing-file enabled?
        btn_select_file.config(state="normal" if not is_dummy else "disabled")
        file_path_label.config(fg="gray" if not is_dummy else "#808080")

        # dummy fields enabled?
        state = "normal" if is_dummy else "disabled"
        name_entry.config(state=state)
        size_box.config(state=state)

    mode.trace("w", update_mode)
    update_mode()

    root.mainloop()

if __name__ == "__main__":
    open_host_gui()
