import os
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

BCOLOR = "#2b2b2b"
FCOLOR = "#3b3b3b"
LOG_BG = "#1e1e1e"
LOG_FG = "#d4d4d4"


class P2PGUI:
    def __init__(self, event_queue, on_file_selected_callback, server=None):
        self.event_queue = event_queue
        self.on_file_selected = on_file_selected_callback
        self.server = server
        self._selected_client_id = None
        self._active_transfer = None

        self.root = TkinterDnD.Tk()
        self.root.title("P2P File Transfer - Dashboard")
        self.root.geometry("880x620")
        self.root.configure(bg=BCOLOR)

        self._setup_styles()
        self._setup_ui()
        self.root.after(100, self._poll_events)

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=FCOLOR, fieldbackground=FCOLOR,
                        foreground="#e0e0e0", rowheight=22)
        style.configure("Treeview.Heading", background=BCOLOR, foreground="#e0e0e0",
                        relief="flat")
        style.map("Treeview", background=[("selected", "#4a6b8a")])
        style.configure("Horizontal.TProgressbar", background="#4CAF50",
                        troughcolor=FCOLOR)

    def _setup_ui(self):
        root = self.root

        self.status_label = tk.Label(root, text="Gotowy", bg=BCOLOR, fg="#888888",
                                     font=("Arial", 10), anchor="w")
        self.status_label.pack(fill=tk.X, padx=12, pady=(8, 0))

        self.drop_frame = tk.Frame(root, bg=FCOLOR, relief=tk.RAISED, bd=2, height=80)
        self.drop_frame.pack(pady=(6, 8), padx=12, fill=tk.X)
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="Przeciągnij plik tutaj\nlub kliknij, aby wybrać",
            bg=FCOLOR, fg="white", font=("Arial", 12), cursor="hand2",
        )
        self.drop_label.pack(expand=True, fill=tk.BOTH)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_label.bind("<Button-1>", lambda e: self._browse_file())

        main = tk.Frame(root, bg=BCOLOR)
        main.pack(fill=tk.BOTH, expand=True, padx=12)

        self._setup_devices_panel(main)
        self._setup_transfer_panel(main)
        self._setup_log_panel(root)

    def _setup_devices_panel(self, parent):
        frame = tk.Frame(parent, bg=BCOLOR)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Połączone urządzenia", bg=BCOLOR, fg="#ffffff",
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 4))

        columns = ("ip", "client_id", "connected_at")
        self.device_tree = ttk.Treeview(frame, columns=columns, show="headings", height=8)
        self.device_tree.heading("ip", text="IP")
        self.device_tree.heading("client_id", text="ID")
        self.device_tree.heading("connected_at", text="Czas połączenia")
        self.device_tree.column("ip", width=120, anchor="w")
        self.device_tree.column("client_id", width=220, anchor="w")
        self.device_tree.column("connected_at", width=130, anchor="w")
        self.device_tree.pack(fill=tk.BOTH, expand=True)

        self.device_tree.bind("<<TreeviewSelect>>", self._on_device_selected)

        self.target_label = tk.Label(frame, text="Cel: brak (wyślij do pierwszego klienta)",
                                     bg=BCOLOR, fg="#888888", font=("Arial", 9))
        self.target_label.pack(anchor="w", pady=(6, 0))

    def _setup_transfer_panel(self, parent):
        frame = tk.Frame(parent, bg=BCOLOR, width=340)
        frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(12, 0))
        frame.pack_propagate(False)

        tk.Label(frame, text="Transfer", bg=BCOLOR, fg="#ffffff",
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 4))

        self.file_name_label = tk.Label(frame, text="Brak aktywnego transferu",
                                        bg=BCOLOR, fg="#cccccc", font=("Arial", 10),
                                        wraplength=330, anchor="w", justify="left")
        self.file_name_label.pack(fill=tk.X, pady=(6, 2))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(4, 2))

        self.transfer_state_label = tk.Label(frame, text="", bg=BCOLOR, fg="#888888",
                                             font=("Arial", 9))
        self.transfer_state_label.pack(anchor="w")

        self.speed_label = tk.Label(frame, text="Prędkość: --", bg=BCOLOR, fg="#4CAF50",
                                    font=("Arial", 10))
        self.speed_label.pack(anchor="w", pady=(4, 0))

        self.eta_label = tk.Label(frame, text="Pozostało: --", bg=BCOLOR, fg="#888888",
                                  font=("Arial", 10))
        self.eta_label.pack(anchor="w")

    def _setup_log_panel(self, root):
        frame = tk.Frame(root, bg=BCOLOR)
        frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        tk.Label(frame, text="Dziennik zdarzeń", bg=BCOLOR, fg="#ffffff",
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(frame, height=8, bg=LOG_BG, fg=LOG_FG,
                                font=("Consolas", 9), relief=tk.FLAT, state="disabled",
                                insertbackground=LOG_FG)
        self.log_text.pack(fill=tk.X)

    def show_error(self, msg):
        self.status_label.config(text=f"Błąd: {msg}", fg="#ff4d4d")
        self.transfer_state_label.config(text=f"Błąd: {msg}", fg="#ff4d4d")
        messagebox.showerror("Błąd", msg)

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def _on_device_selected(self, _event):
        selection = self.device_tree.selection()
        if not selection:
            return
        self._selected_client_id = selection[0]
        addr = self.device_tree.item(selection[0], "values")[0]
        self.target_label.config(text=f"Cel: {self._selected_client_id} ({addr})",
                                 fg="#4CAF50")

    def _on_drop(self, event):
        filepath = event.data.strip("{}").strip('"').strip("'")
        self._start_send(filepath)

    def _browse_file(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self._start_send(filepath)

    def _start_send(self, filepath):
        client_id = self._selected_client_id
        self.status_label.config(text=f"Plik: {os.path.basename(filepath)}", fg="#4CAF50")
        if self.on_file_selected:
            self.on_file_selected(filepath, client_id)

    def _poll_events(self):
        try:
            while True:
                event_type, data = self.event_queue.get_nowait()
                handler = getattr(self, f"_on_{event_type}", None)
                if handler:
                    handler(data)
        except queue.Empty:
            pass
        self._refresh_devices()
        self._refresh_transfer()
        self.root.after(100, self._poll_events)

    def _on_log(self, data):
        self._log(data.get("message", ""))

    def _on_client_connected(self, data):
        addr = data.get("addr")
        self._log(f"Urządzenie połączone: {addr}")

    def _on_client_disconnected(self, data):
        self._log(f"Urządzenie rozłączone: {data.get('client_id')}")

    def _on_transfer_progress(self, data):
        self._active_transfer = {
            "filename": data.get("filename"),
            "sent": data.get("sent", 0),
            "total": data.get("total", 1),
            "speed_mbps": data.get("speed_mbps", 0.0),
            "direction": data.get("direction", ""),
            "ok": None,
        }

    def _on_transfer_complete(self, data):
        total = data.get("total", 1)
        self._active_transfer = {
            "filename": data.get("filename"),
            "sent": total,
            "total": total,
            "speed_mbps": 0.0,
            "direction": data.get("direction", ""),
            "ok": bool(data.get("ok")),
            "error": data.get("error"),
        }

    def _refresh_transfer(self):
        t = self._active_transfer
        if t is None:
            self.file_name_label.config(text="Brak aktywnego transferu")
            self.progress_var.set(0.0)
            self.transfer_state_label.config(text="", fg="#888888")
            self.speed_label.config(text="Prędkość: --", fg="#4CAF50")
            self.eta_label.config(text="Pozostało: --")
            return

        total = t.get("total") or 1
        sent = t.get("sent", 0)
        pct = min(100.0, 100.0 * sent / total)
        self.progress_var.set(pct)
        direction = "Serwer -> Klient" if t.get("direction") == "send" else "Klient -> Serwer"
        self.file_name_label.config(text=f"{t['filename']}  ({direction})")

        if t.get("ok") is True:
            self.transfer_state_label.config(text="Zakończono pomyślnie", fg="#4CAF50")
            self.speed_label.config(text="Prędkość: --", fg="#4CAF50")
            self.eta_label.config(text="Pozostało: --")
        elif t.get("ok") is False:
            self.transfer_state_label.config(text=f"Błąd: {t.get('error', 'nieznany')}",
                                             fg="#ff4d4d")
            self.speed_label.config(text="Prędkość: --", fg="#4CAF50")
            self.eta_label.config(text="Pozostało: --")
        else:
            speed = t.get("speed_mbps", 0.0)
            self.transfer_state_label.config(text=f"{pct:.1f}% ukończone", fg="#cccccc")
            self.speed_label.config(text=f"Prędkość: {speed:.2f} MB/s", fg="#4CAF50")
            if speed > 0:
                remaining_sec = (total - sent) / (speed * 1_000_000)
                self.eta_label.config(text=f"Pozostało: {remaining_sec:.0f} s")
            else:
                self.eta_label.config(text="Pozostało: --")

    def _refresh_devices(self):
        if self.server is None:
            return
        snapshot = self.server.get_clients_snapshot()
        known_ids = {s["client_id"] for s in snapshot}
        for item in self.device_tree.get_children():
            if item not in known_ids:
                self.device_tree.delete(item)
        for s in snapshot:
            if self.device_tree.exists(s["client_id"]):
                continue
            addr = f"{s['addr'][0]}:{s['addr'][1]}"
            connected_at = time.strftime("%H:%M:%S", time.localtime(s["connected_at"]))
            self.device_tree.insert("", tk.END, iid=s["client_id"],
                                    values=(addr, s["client_id"], connected_at))
        if self._selected_client_id is not None and self._selected_client_id not in known_ids:
            self._selected_client_id = None
            self.target_label.config(text="Cel: brak (wyślij do pierwszego klienta)",
                                     fg="#888888")

    def run(self):
        self.root.mainloop()
