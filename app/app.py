import sys
import os
import json
import time
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import websocket

from collector import collect_all

COLLECT_INTERVAL = 2.0
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8765


def _request_admin():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
        )
        sys.exit()


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {"host": DEFAULT_HOST, "port": DEFAULT_PORT}


def save_settings(host: str, port: int):
    with open(SETTINGS_PATH, "w") as f:
        json.dump({"host": host, "port": port}, f, indent=2)


def format_data(data: dict) -> str:
    lines = []

    sys_info = data.get("system", {})
    if sys_info:
        lines.append("=== System Info ===")
        lines.append(f"Timestamp:  {sys_info.get('timestamp', 'N/A')}")
        lines.append(f"User:       {sys_info.get('user', 'N/A')}")
        lines.append(f"Platform:   {sys_info.get('platform', 'N/A')}")
        lines.append(f"Hostname:   {sys_info.get('hostname', 'N/A')}")
        lines.append(f"Boot Time:  {sys_info.get('boot_time', 'N/A')}")

    cpu = data.get("cpu", {})
    if cpu:
        lines.append("")
        lines.append("=== CPU Info ===")
        temp = cpu.get("temperature_c")
        lines.append(f"Temperature:      {f'{temp:.1f} °C' if temp is not None else 'N/A'}")
        lines.append(f"Physical Cores:   {cpu.get('physical_cores', 'N/A')}")
        lines.append(f"Total Cores:      {cpu.get('total_cores', 'N/A')}")
        max_f, min_f, cur_f = cpu.get("max_freq_mhz"), cpu.get("min_freq_mhz"), cpu.get("current_freq_mhz")
        if max_f: lines.append(f"Max Frequency:    {max_f:.2f} MHz")
        if min_f: lines.append(f"Min Frequency:    {min_f:.2f} MHz")
        if cur_f: lines.append(f"Current Freq:     {cur_f:.2f} MHz")
        lines.append(f"Total Usage:      {cpu.get('total_usage_pct', 'N/A')}%")
        for i, pct in enumerate(cpu.get("per_core_usage_pct", [])):
            lines.append(f"  Core {i}: {pct}%")
        for name, rpm in cpu.get("fans_rpm", {}).items():
            lines.append(f"  {name}: {rpm} RPM")

    mem = data.get("memory", {})
    if mem:
        lines.append("")
        lines.append("=== Memory Info ===")
        lines.append(f"Total:       {mem.get('total_mb', 'N/A')} MB")
        lines.append(f"Available:   {mem.get('available_mb', 'N/A')} MB")
        lines.append(f"Used:        {mem.get('used_mb', 'N/A')} MB ({mem.get('used_pct', 'N/A')}%)")
        lines.append(f"Swap Total:  {mem.get('swap_total_mb', 'N/A')} MB")
        lines.append(f"Swap Used:   {mem.get('swap_used_mb', 'N/A')} MB ({mem.get('swap_used_pct', 'N/A')}%)")

    disks = data.get("disk", [])
    if disks:
        lines.append("")
        lines.append("=== Disk Info ===")
        for d in disks:
            lines.append(f"{d.get('drive', '?')} — Total: {d.get('total_gb', 'N/A')} GB, Free: {d.get('free_gb', 'N/A')} GB")

    network = data.get("network", [])
    if network:
        lines.append("")
        lines.append("=== Network Info ===")
        for iface in network:
            lines.append(f"  {iface.get('interface', '?')}: {iface.get('address', 'N/A')}")

    battery = data.get("battery")
    if battery:
        lines.append("")
        lines.append("=== Battery Info ===")
        lines.append(f"Percent:    {battery.get('percent', 'N/A')}%")
        lines.append(f"Plugged In: {'Yes' if battery.get('plugged_in') else 'No'}")

    gpu = data.get("gpu", {})
    if gpu:
        lines.append("")
        lines.append("=== GPU Info ===")
        temp = gpu.get("temperature_c")
        lines.append(f"Temperature: {f'{temp:.1f} °C' if temp is not None else 'N/A'}")
        fans = gpu.get("fans_rpm", {})
        for name, rpm in fans.items():
            lines.append(f"  {name}: {rpm} RPM")
        if not fans:
            lines.append("  Fan speed: N/A")

    boards = data.get("motherboard", [])
    if boards:
        lines.append("")
        lines.append("=== Motherboard Info ===")
        for b in boards:
            lines.append(f"Manufacturer: {b.get('manufacturer', 'N/A')}")
            lines.append(f"Product:      {b.get('product', 'N/A')}")
            lines.append(f"Serial:       {b.get('serial', 'N/A')}")

    return "\n".join(lines)


class PyMonitorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PyMonitor - System Hardware Monitor")
        try:
            self.root.iconbitmap("assets/monitor.ico")
        except Exception:
            pass

        settings = load_settings()

        outer = ttk.Frame(root, padding="10")
        outer.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))

        # ── Connection bar ────────────────────────────────────────────────────
        conn_frame = ttk.LabelFrame(outer, text="Backend connection", padding="6 4")
        conn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        ttk.Label(conn_frame, text="Host:").grid(row=0, column=0, padx=(0, 4))
        self._host_var = tk.StringVar(value=settings["host"])
        host_entry = ttk.Entry(conn_frame, textvariable=self._host_var, width=20)
        host_entry.grid(row=0, column=1, padx=(0, 8))

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, padx=(0, 4))
        self._port_var = tk.StringVar(value=str(settings["port"]))
        port_entry = ttk.Entry(conn_frame, textvariable=self._port_var, width=6)
        port_entry.grid(row=0, column=3, padx=(0, 12))

        ttk.Button(conn_frame, text="Connect", command=self._apply_connection).grid(row=0, column=4, padx=(0, 16))

        self._status_var = tk.StringVar(value="Connecting…")
        ttk.Label(conn_frame, textvariable=self._status_var, foreground="gray").grid(row=0, column=5, sticky=tk.W)

        # Reconnect on Enter in either entry
        host_entry.bind("<Return>", lambda _: self._apply_connection())
        port_entry.bind("<Return>", lambda _: self._apply_connection())

        # ── Output ────────────────────────────────────────────────────────────
        self.output = scrolledtext.ScrolledText(
            outer, width=100, height=40, font=("Consolas", 10)
        )
        self.output.config(state=tk.DISABLED)
        self.output.grid(row=1, column=0, pady=(0, 8))

        ttk.Button(outer, text="Exit", command=root.quit).grid(row=2, column=0, sticky=tk.E)

        # ── Start ─────────────────────────────────────────────────────────────
        self._ws: websocket.WebSocketApp | None = None
        self._ws_open = False

        self._connect(self._build_url())
        threading.Thread(target=self._collect_loop, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_url(self) -> str:
        host = self._host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self._port_var.get().strip())
        except ValueError:
            port = DEFAULT_PORT
        return f"ws://{host}:{port}"

    def _apply_connection(self):
        host = self._host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self._port_var.get().strip())
        except ValueError:
            port = DEFAULT_PORT
        save_settings(host, port)
        self._host_var.set(host)
        self._port_var.set(str(port))
        if self._ws:
            self._ws.close()
        self._connect(f"ws://{host}:{port}")

    # ── WebSocket ─────────────────────────────────────────────────────────────

    def _connect(self, url: str):
        def on_open(ws):
            self._ws_open = True
            self.root.after(0, self._status_var.set, f"Connected  →  {url}")

        def on_error(ws, err):
            self._ws_open = False
            self.root.after(0, self._status_var.set, f"Error: {err}")

        def on_close(ws, code, msg):
            self._ws_open = False
            self.root.after(0, self._status_var.set, "Disconnected — retrying in 3s…")
            self.root.after(3000, lambda: self._connect(url))

        self._ws = websocket.WebSocketApp(
            url, on_open=on_open, on_error=on_error, on_close=on_close
        )
        threading.Thread(target=self._ws.run_forever, daemon=True).start()

    # ── Collection loop ───────────────────────────────────────────────────────

    def _collect_loop(self):
        while True:
            data = collect_all()
            self.root.after(0, self._update_display, format_data(data))
            if self._ws_open and self._ws:
                try:
                    self._ws.send(json.dumps(data))
                except Exception:
                    pass
            time.sleep(COLLECT_INTERVAL)

    # ── Display ───────────────────────────────────────────────────────────────

    def _update_display(self, text: str):
        scroll_pos = self.output.yview()
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.config(state=tk.DISABLED)
        self.output.yview_moveto(scroll_pos[0])


if __name__ == "__main__":
    _request_admin()
    root = tk.Tk()
    PyMonitorApp(root)
    root.mainloop()
