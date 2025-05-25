# PyMonitor

**PyMonitor** is a Windows system hardware and resource monitor with a simple graphical interface. It gathers and displays information about your CPU, memory, disks, GPU, motherboard, battery, and network interfaces. This tool is useful for getting a quick overview of your machine’s health and specs, especially if you need more detail than Task Manager provides.

## Features

- Displays system info: OS, hostname, user, and boot time
- Shows CPU stats, including per-core usage, temperature, and frequencies
- Reports memory and swap usage
- Lists disk sizes and free space (via WMI for best Windows compatibility)
- Reveals network interface addresses
- Shows battery status if present
- Reads GPU temperature and (for NVIDIA cards) fan speed
- Includes motherboard info (manufacturer, product, serial)
- All info is presented in a scrollable, refreshable GUI

## Requirements

- Python 3.7 or newer (tested on Windows)
- [See `requirements.txt`](./requirements.txt), which includes:
  - `psutil`
  - `wmi`
  - `pynvml`
  - `WinTmp` (custom module, see below)
  - `tk` (Tkinter is included with most Python distributions, but may require `python3-tk` on Linux)

Install dependencies with:
```sh
pip install -r requirements.txt
```

## Usage

1. Make sure you have all dependencies installed.
2. **Run as administrator** for full hardware readings (especially temperatures and fan speeds).
3. Execute the script:

```sh
python gui_monitor.py
```

The main window will show all collected stats. Click **Refresh** to update the display.

## Notes

- **WinTmp**: This is a custom or third-party module used for temperature readings. If you don’t have it, you may need to write or obtain a replacement. The rest of the tool works without it, but CPU and GPU temperatures won't show.
- **GPU Info**: NVIDIA GPU data requires `pynvml` and a compatible driver. Other GPUs will only show basic info.
- **Motherboard Info**: Uses WMI, so only the basics are shown. Some fields may be missing depending on your hardware.

## Screenshot

TO do

## License

MIT License (see [LICENSE](./LICENSE))

---

If you have issues or suggestions, feel free to open an issue or fork the project!
