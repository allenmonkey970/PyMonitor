import psutil
import WinTmp
import ctypes
import platform
import getpass
import datetime
import wmi

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

if not is_admin():
    print("Please run this script as a system administrator for accurate hardware readings.")

# System Info
print("System Info")
print(f"Platform: {platform.system()} {platform.release()}")
print(f"Hostname: {platform.node()}")
print(f"User: {getpass.getuser()}")
print(f"Boot Time: {datetime.datetime.fromtimestamp(psutil.boot_time())}")

# CPU Info
print("\nCPU Info")
print("CPU Temperature:", WinTmp.CPU_Temp())
print(f"Physical cores: {psutil.cpu_count(logical=False)}")
print(f"Total cores: {psutil.cpu_count(logical=True)}")
cpufreq = psutil.cpu_freq()
if cpufreq:
    print(f"Max Frequency: {cpufreq.max:.2f} MHz")
    print(f"Min Frequency: {cpufreq.min:.2f} MHz")
    print(f"Current Frequency: {cpufreq.current:.2f} MHz")

print("\nCPU Usage Per Core:")
for i, percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
    print(f"Core {i}: {percentage}%")
print(f"Total CPU Usage: {psutil.cpu_percent()}%")

# Memory Info
mem = psutil.virtual_memory()
print("\nMemory Info")
print(f"Total: {mem.total // (1024 ** 2)} MB")
print(f"Available: {mem.available // (1024 ** 2)} MB")
print(f"Used: {mem.used // (1024 ** 2)} MB ({mem.percent}%)")
swap = psutil.swap_memory()
print(f"Swap Total: {swap.total // (1024 ** 2)} MB")
print(f"Swap Used: {swap.used // (1024 ** 2)} MB ({swap.percent}%)")

# Disk Info
print("\nDisk Info")
c = wmi.WMI()
for disk in c.Win32_LogicalDisk(DriveType=3):  # 3 = Local Disk
    print(f"{disk.DeviceID} - Total: {int(disk.Size) // (1024 ** 3)} GB, "
          f"Free: {int(disk.FreeSpace) // (1024 ** 3)} GB")

# Network Info
print("\nNetwork Info")
print("Network Interfaces and IPs:")
for interface, addrs in psutil.net_if_addrs().items():
    for addr in addrs:
        if hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
            continue
        if hasattr(psutil, "AF_PACKET") and addr.family == psutil.AF_PACKET:
            continue
        print(f"  {interface}: {addr.address}")

# Battery Info
if hasattr(psutil, "sensors_battery"):
    battery = psutil.sensors_battery()
    if battery:
        print("\nBattery Info")
        print(f"Percent: {battery.percent}%")
        print(f"Plugged In: {'Yes' if battery.power_plugged else 'No'}")

# GPU Info
print("\nGPU Info")
print("GPU Temperature:", WinTmp.GPU_Temp())

if has_pynvml:
    print("\nGPU Fan Info (NVIDIA only):")
    try:
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        for i in range(device_count):
            handle = nvmlDeviceGetHandleByIndex(i)
            name = nvmlDeviceGetName(handle)
            try:
                fan_speed = nvmlDeviceGetFanSpeed(handle)
                print(f"GPU {i} ({name}): Fan Speed: {fan_speed}%")
            except NVMLError_NotSupported:
                print(f"GPU {i} ({name}): Fan speed reading not supported.")
            except Exception as e:
                print(f"GPU {i} ({name}): Error reading fan speed: {e}")
        nvmlShutdown()
    except Exception as e:
        print(f"Could not read NVIDIA GPU fan info: {e}")
else:
    print("\nGPU Fan Info: pynvml not installed. Install with 'pip install nvidia-ml-py3' to get NVIDIA GPU fan speed.")

# Motherboard Info (Windows only, basic)
try:
    import wmi
    c = wmi.WMI()
    print("\nMotherboard Info")
    for board in c.Win32_BaseBoard():
        print(f"Manufacturer: {board.Manufacturer}")
        print(f"Product: {board.Product}")
        print(f"Serial Number: {board.SerialNumber}")
except ImportError:
    print("\nMotherboard Info: Install 'wmi' package for basic motherboard info.")
except Exception as e:
    print(f"\nMotherboard Info: Could not retrieve ({e})")