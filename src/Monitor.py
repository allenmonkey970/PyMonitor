import sys
import psutil
import ctypes
import platform
import getpass
import datetime
import threading
import wmi
import tkinter as tk
from tkinter import ttk, scrolledtext

def _request_admin():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
        )
        sys.exit()

_request_admin()

try:
    from HardwareMonitor.Hardware import Computer, HardwareType, SensorType

    _hw_computer = Computer()
    _hw_computer.IsCpuEnabled = True
    _hw_computer.IsGpuEnabled = True
    _hw_computer.Open()
    has_hw_monitor = True
except Exception:
    has_hw_monitor = False
    _hw_computer = None


def _get_hw_sensors(hw_types, sensor_type, name_hint=None):
    """Return list of (name, value) tuples for matching sensors."""
    if not has_hw_monitor or _hw_computer is None:
        return []
    results = []
    try:
        for hardware in _hw_computer.Hardware:
            if hardware.HardwareType not in hw_types:
                continue
            hardware.Update()
            for sub in hardware.SubHardware:
                sub.Update()
            for sensor in hardware.Sensors:
                if sensor.SensorType != sensor_type:
                    continue
                if sensor.Value is None:
                    continue
                if name_hint and name_hint.lower() not in sensor.Name.lower():
                    continue
                results.append((sensor.Name, sensor.Value))
    except Exception:
        pass
    return results


def _get_hw_temp(hw_types, sensor_name_hint=None):
    if not has_hw_monitor or _hw_computer is None:
        return "N/A"
    sensors = _get_hw_sensors(hw_types, SensorType.Temperature)
    if not sensors:
        return "N/A"
    if sensor_name_hint:
        for name, value in sensors:
            if sensor_name_hint.lower() in name.lower():
                return f"{value:.1f} °C"
    return f"{sensors[0][1]:.1f} °C"


def CPU_Temp():
    return _get_hw_temp([HardwareType.Cpu] if has_hw_monitor else [], "package")


def GPU_Temp():
    gpu_types = []
    if has_hw_monitor:
        for attr in ("GpuNvidia", "GpuAmd", "GpuIntel", "Gpu"):
            val = getattr(HardwareType, attr, None)
            if val is not None:
                gpu_types.append(val)
    return _get_hw_temp(gpu_types, "gpu core")


_cpu_percent_per_core = []
_cpu_percent_total = 0.0
_cpu_lock = threading.Lock()


def _cpu_sampler():
    global _cpu_percent_per_core, _cpu_percent_total
    psutil.cpu_percent(percpu=True, interval=None)  # prime
    while True:
        per_core = psutil.cpu_percent(percpu=True, interval=1)
        total = psutil.cpu_percent(interval=None)
        with _cpu_lock:
            _cpu_percent_per_core = per_core
            _cpu_percent_total = total


threading.Thread(target=_cpu_sampler, daemon=True).start()


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_system_info():
    lines = []
    lines.append("System Info")

    # Use timezone-aware datetime to avoid deprecation warning
    if hasattr(datetime, "UTC"):
        # Python 3.11+ way
        current_utc = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    else:
        # Older Python versions
        current_utc = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"Current Date and Time: {current_utc}")

    # Add current user login
    current_user = getpass.getuser()
    lines.append(f"Current User's Login: {current_user}")

    lines.append(f"Platform: {platform.system()} {platform.release()}")
    lines.append(f"Hostname: {platform.node()}")
    lines.append(f"Boot Time: {datetime.datetime.fromtimestamp(psutil.boot_time())}")
    return "\n".join(lines)


def get_cpu_info():
    lines = []
    lines.append("CPU Info")
    lines.append(f"CPU Temperature: {CPU_Temp()}")
    lines.append(f"Physical cores: {psutil.cpu_count(logical=False)}")
    lines.append(f"Total cores: {psutil.cpu_count(logical=True)}")
    cpufreq = psutil.cpu_freq()
    if cpufreq:
        lines.append(f"Max Frequency: {cpufreq.max:.2f} MHz")
        lines.append(f"Min Frequency: {cpufreq.min:.2f} MHz")
        lines.append(f"Current Frequency: {cpufreq.current:.2f} MHz")
    lines.append("CPU Usage Per Core:")
    with _cpu_lock:
        per_core = list(_cpu_percent_per_core)
        total = _cpu_percent_total
    for i, percentage in enumerate(per_core):
        lines.append(f"  Core {i}: {percentage}%")
    lines.append(f"Total CPU Usage: {total}%")
    return "\n".join(lines)


def get_cpu_fan_info():
    lines = []
    lines.append("CPU Fan Info")

    cpu_types = [HardwareType.Cpu] if has_hw_monitor else []
    fans = _get_hw_sensors(cpu_types, SensorType.Fan)
    if fans:
        for name, value in fans:
            lines.append(f"{name}: {value:.0f} RPM")
        return "\n".join(lines)

    lines.append("CPU fan speed not available.")
    return "\n".join(lines)


def get_memory_info():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    lines = []
    lines.append("Memory Info")
    lines.append(f"Total: {mem.total // (1024 ** 2)} MB")
    lines.append(f"Available: {mem.available // (1024 ** 2)} MB")
    lines.append(f"Used: {mem.used // (1024 ** 2)} MB ({mem.percent}%)")
    lines.append(f"Swap Total: {swap.total // (1024 ** 2)} MB")
    lines.append(f"Swap Used: {swap.used // (1024 ** 2)} MB ({swap.percent}%)")
    return "\n".join(lines)


def get_disk_info():
    lines = []
    c = wmi.WMI()
    lines.append("Disk Info")
    for disk in c.Win32_LogicalDisk(DriveType=3):
        try:
            size = int(disk.Size) // (1024 ** 3)
            free = int(disk.FreeSpace) // (1024 ** 3)
            lines.append(f"{disk.DeviceID} - Total: {size} GB, Free: {free} GB")
        except Exception as e:
            lines.append(f"Error reading {disk.DeviceID}: {e}")
    return "\n".join(lines)


def get_network_info():
    lines = []
    lines.append("Network Info")
    lines.append("Network Interfaces and IPs:")
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                continue
            if hasattr(psutil, "AF_PACKET") and addr.family == psutil.AF_PACKET:
                continue
            lines.append(f"  {interface}: {addr.address}")
    return "\n".join(lines)


def get_battery_info():
    lines = []
    if hasattr(psutil, "sensors_battery"):
        battery = psutil.sensors_battery()
        if battery:
            lines.append("Battery Info")
            lines.append(f"Percent: {battery.percent}%")
            lines.append(f"Plugged In: {'Yes' if battery.power_plugged else 'No'}")
    return "\n".join(lines)


def get_gpu_info():
    lines = []
    lines.append("GPU Info")
    lines.append(f"GPU Temperature: {GPU_Temp()}")

    gpu_types = []
    if has_hw_monitor:
        for attr in ("GpuNvidia", "GpuAmd", "GpuIntel", "Gpu"):
            val = getattr(HardwareType, attr, None)
            if val is not None:
                gpu_types.append(val)

    fans = _get_hw_sensors(gpu_types, SensorType.Fan)
    if fans:
        for name, value in fans:
            lines.append(f"{name}: {value:.0f} RPM")
    else:
        lines.append("GPU fan speed not available.")

    return "\n".join(lines)


def get_motherboard_info():
    lines = []
    try:
        c = wmi.WMI()
        lines.append("Motherboard Info")
        for board in c.Win32_BaseBoard():
            lines.append(f"Manufacturer: {board.Manufacturer}")
            lines.append(f"Product: {board.Product}")
            lines.append(f"Serial Number: {board.SerialNumber}")
    except ImportError:
        lines.append("Motherboard Info: Install 'wmi' package for basic motherboard info.")
    except Exception as e:
        lines.append(f"Motherboard Info: Could not retrieve ({e})")
    return "\n".join(lines)


_refresh_job = None
_refreshing = False


def _collect_info():
    sections = [
        get_system_info(),
        get_cpu_info(),
        get_cpu_fan_info(),
        get_memory_info(),
        get_disk_info(),
        get_network_info(),
        get_battery_info(),
        get_gpu_info(),
        get_motherboard_info(),
    ]
    return "\n\n".join(sections)


def _apply_update(text):
    global _refreshing
    scroll_pos = output.yview()
    output.config(state=tk.NORMAL)
    output.delete('1.0', tk.END)
    output.insert(tk.END, text)
    output.config(state=tk.DISABLED)
    output.yview_moveto(scroll_pos[0])
    _refreshing = False
    _schedule_refresh()


def _run_refresh():
    text = _collect_info()
    root.after(0, _apply_update, text)


def _schedule_refresh():
    global _refresh_job
    _refresh_job = root.after(2000, _trigger_refresh)


def _trigger_refresh():
    global _refreshing
    if _refreshing:
        _schedule_refresh()
        return
    _refreshing = True
    threading.Thread(target=_run_refresh, daemon=True).start()


def manual_refresh():
    global _refresh_job, _refreshing
    if _refresh_job is not None:
        root.after_cancel(_refresh_job)
        _refresh_job = None
    if not _refreshing:
        _refreshing = True
        threading.Thread(target=_run_refresh, daemon=True).start()


# Tkinter GUI setup
root = tk.Tk()
root.title("PyMonitor - System Hardware Monitor")
root.iconbitmap("monitor.ico")

mainframe = ttk.Frame(root, padding="10")
mainframe.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))

output = scrolledtext.ScrolledText(mainframe, width=100, height=40, font=("Consolas", 10))
output.config(state=tk.DISABLED)
output.grid(row=0, column=0, columnspan=2, pady=(0, 10))

refresh_button = ttk.Button(mainframe, text="Refresh", command=manual_refresh)
refresh_button.grid(row=1, column=0, sticky=tk.W)

exit_button = ttk.Button(mainframe, text="Exit", command=root.quit)
exit_button.grid(row=1, column=1, sticky=tk.E)

_trigger_refresh()

root.mainloop()