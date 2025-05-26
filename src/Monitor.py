import psutil
import WinTmp
import ctypes
import platform
import getpass
import datetime
import wmi
import tkinter as tk
from tkinter import ttk, scrolledtext

try:
    import pynvml
    from pynvml import (
        nvmlInit, nvmlShutdown, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetName, nvmlDeviceGetFanSpeed, NVMLError_NotSupported
    )

    has_pynvml = True
except ImportError:
    has_pynvml = False


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
    lines.append(f"CPU Temperature: {WinTmp.CPU_Temp()}")
    lines.append(f"Physical cores: {psutil.cpu_count(logical=False)}")
    lines.append(f"Total cores: {psutil.cpu_count(logical=True)}")
    cpufreq = psutil.cpu_freq()
    if cpufreq:
        lines.append(f"Max Frequency: {cpufreq.max:.2f} MHz")
        lines.append(f"Min Frequency: {cpufreq.min:.2f} MHz")
        lines.append(f"Current Frequency: {cpufreq.current:.2f} MHz")
    lines.append("CPU Usage Per Core:")
    for i, percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
        lines.append(f"  Core {i}: {percentage}%")
    lines.append(f"Total CPU Usage: {psutil.cpu_percent()}%")
    return "\n".join(lines)


def get_cpu_fan_info():
    lines = []
    lines.append("CPU Fan Info")

    fan_found = False

    try:
        c = wmi.WMI()
        for temp in c.Win32_TemperatureProbe():
            if 'CPU' in temp.Description and hasattr(temp, 'CurrentReading'):
                lines.append(f"CPU Fan: {temp.CurrentReading} RPM")
                fan_found = True
    except Exception as e:
        lines.append(f"Standard WMI approach failed: {e}")

    if not fan_found:
        try:
            c = wmi.WMI(namespace=r"root\CIMV2")
            for fan in c.Win32_Fan():
                lines.append(f"Fan: {fan.Name}, Speed: {fan.DesiredSpeed} RPM")
                fan_found = True
        except Exception as e:
            pass

    if not fan_found:
        try:
            c = wmi.WMI(namespace=r"root\WMI")
            for item in c.MSAcpi_ThermalZoneTemperature():
                if hasattr(item, 'ActiveCooling') and item.ActiveCooling:
                    lines.append(f"Thermal Zone: {item.InstanceName} has active cooling")
                    fan_found = True
        except Exception as e:
            pass

    if not fan_found:
        lines.append("CPU Fan info not available through Windows Management Instrumentation (WMI).")

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
    lines.append(f"GPU Temperature: {WinTmp.GPU_Temp()}")
    if has_pynvml:
        try:
            nvmlInit()
            device_count = nvmlDeviceGetCount()
            for i in range(device_count):
                handle = nvmlDeviceGetHandleByIndex(i)
                name = nvmlDeviceGetName(handle)
                try:
                    fan_speed = nvmlDeviceGetFanSpeed(handle)
                    lines.append(
                        f"GPU {i} ({name.decode('utf-8') if isinstance(name, bytes) else name}): Fan Speed: {fan_speed}%")
                except NVMLError_NotSupported:
                    lines.append(
                        f"GPU {i} ({name.decode('utf-8') if isinstance(name, bytes) else name}): Fan speed reading not supported.")
                except Exception as e:
                    lines.append(
                        f"GPU {i} ({name.decode('utf-8') if isinstance(name, bytes) else name}): Error reading fan speed: {e}")
            nvmlShutdown()
        except Exception as e:
            lines.append(f"Could not read NVIDIA GPU fan info: {e}")
    else:
        lines.append(
            "GPU Fan Info: pynvml not installed. Install with 'pip install nvidia-ml-py3' to get NVIDIA GPU fan speed.")
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


def show_all_info():
    output.delete('1.0', tk.END)
    if not is_admin():
        output.insert(tk.END, "Please run this script as a system administrator for accurate hardware readings.\n\n")
    output.insert(tk.END, get_system_info() + "\n\n")
    output.insert(tk.END, get_cpu_info() + "\n\n")
    output.insert(tk.END, get_cpu_fan_info() + "\n\n")
    output.insert(tk.END, get_memory_info() + "\n\n")
    output.insert(tk.END, get_disk_info() + "\n\n")
    output.insert(tk.END, get_network_info() + "\n\n")
    output.insert(tk.END, get_battery_info() + "\n\n")
    output.insert(tk.END, get_gpu_info() + "\n\n")
    output.insert(tk.END, get_motherboard_info() + "\n\n")


# Tkinter GUI setup
root = tk.Tk()
root.title("PyMonitor - System Hardware Monitor")

mainframe = ttk.Frame(root, padding="10")
mainframe.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))

output = scrolledtext.ScrolledText(mainframe, width=100, height=40, font=("Consolas", 10))
output.grid(row=0, column=0, columnspan=2, pady=(0, 10))

refresh_button = ttk.Button(mainframe, text="Refresh", command=show_all_info)
refresh_button.grid(row=1, column=0, sticky=tk.W)

exit_button = ttk.Button(mainframe, text="Exit", command=root.quit)
exit_button.grid(row=1, column=1, sticky=tk.E)

show_all_info()

root.mainloop()