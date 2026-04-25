import sys
import json
import psutil
import platform
import getpass
import datetime
import wmi
import ctypes

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
    HardwareType = None
    SensorType = None


def _get_hw_sensors(hw_types, sensor_type, name_hint=None):
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
                results.append((sensor.Name, float(sensor.Value)))
    except Exception:
        pass
    return results


def _get_hw_temp(hw_types, sensor_name_hint=None):
    if not has_hw_monitor or _hw_computer is None:
        return None
    sensors = _get_hw_sensors(hw_types, SensorType.Temperature)
    if not sensors:
        return None
    if sensor_name_hint:
        for name, value in sensors:
            if sensor_name_hint.lower() in name.lower():
                return value
    return sensors[0][1]


def _cpu_types():
    return [HardwareType.Cpu] if has_hw_monitor else []


def _gpu_types():
    types = []
    if has_hw_monitor:
        for attr in ("GpuNvidia", "GpuAmd", "GpuIntel", "Gpu"):
            val = getattr(HardwareType, attr, None)
            if val is not None:
                types.append(val)
    return types


def get_system_info():
    if hasattr(datetime, "UTC"):
        ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "timestamp": ts,
        "user": getpass.getuser(),
        "platform": f"{platform.system()} {platform.release()}",
        "hostname": platform.node(),
        "boot_time": str(datetime.datetime.fromtimestamp(psutil.boot_time())),
    }


def get_cpu_info():
    per_core = psutil.cpu_percent(percpu=True, interval=1)
    total = psutil.cpu_percent(interval=None)
    freq = psutil.cpu_freq()
    temp = _get_hw_temp(_cpu_types(), "package")
    fans = _get_hw_sensors(_cpu_types(), SensorType.Fan) if has_hw_monitor else []
    return {
        "temperature_c": temp,
        "physical_cores": psutil.cpu_count(logical=False),
        "total_cores": psutil.cpu_count(logical=True),
        "max_freq_mhz": round(freq.max, 2) if freq else None,
        "min_freq_mhz": round(freq.min, 2) if freq else None,
        "current_freq_mhz": round(freq.current, 2) if freq else None,
        "per_core_usage_pct": per_core,
        "total_usage_pct": total,
        "fans_rpm": {name: round(val) for name, val in fans},
    }


def get_memory_info():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total_mb": mem.total // (1024 ** 2),
        "available_mb": mem.available // (1024 ** 2),
        "used_mb": mem.used // (1024 ** 2),
        "used_pct": mem.percent,
        "swap_total_mb": swap.total // (1024 ** 2),
        "swap_used_mb": swap.used // (1024 ** 2),
        "swap_used_pct": swap.percent,
    }


def get_disk_info():
    disks = []
    try:
        c = wmi.WMI()
        for disk in c.Win32_LogicalDisk(DriveType=3):
            try:
                disks.append({
                    "drive": disk.DeviceID,
                    "total_gb": int(disk.Size) // (1024 ** 3),
                    "free_gb": int(disk.FreeSpace) // (1024 ** 3),
                })
            except Exception:
                pass
    except Exception:
        pass
    return disks


def get_network_info():
    interfaces = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                continue
            if hasattr(psutil, "AF_PACKET") and addr.family == psutil.AF_PACKET:
                continue
            interfaces.append({"interface": iface, "address": addr.address})
    return interfaces


def get_battery_info():
    if hasattr(psutil, "sensors_battery"):
        bat = psutil.sensors_battery()
        if bat:
            return {
                "percent": bat.percent,
                "plugged_in": bat.power_plugged,
            }
    return None


def get_gpu_info():
    gpu_types = _gpu_types()
    temp = _get_hw_temp(gpu_types, "gpu core")
    fans = _get_hw_sensors(gpu_types, SensorType.Fan) if has_hw_monitor else []
    return {
        "temperature_c": temp,
        "fans_rpm": {name: round(val) for name, val in fans},
    }


def get_motherboard_info():
    try:
        c = wmi.WMI()
        boards = []
        for board in c.Win32_BaseBoard():
            boards.append({
                "manufacturer": board.Manufacturer,
                "product": board.Product,
                "serial": board.SerialNumber,
            })
        return boards
    except Exception:
        return []


def collect_all():
    return {
        "system": get_system_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "network": get_network_info(),
        "battery": get_battery_info(),
        "gpu": get_gpu_info(),
        "motherboard": get_motherboard_info(),
    }


if __name__ == "__main__":
    print(json.dumps(collect_all()))
