export interface SystemInfo {
  timestamp: string;
  user: string;
  platform: string;
  hostname: string;
  boot_time: string;
}

export interface CpuInfo {
  temperature_c: number | null;
  physical_cores: number;
  total_cores: number;
  max_freq_mhz: number | null;
  min_freq_mhz: number | null;
  current_freq_mhz: number | null;
  per_core_usage_pct: number[];
  total_usage_pct: number;
  fans_rpm: Record<string, number>;
}

export interface MemoryInfo {
  total_mb: number;
  available_mb: number;
  used_mb: number;
  used_pct: number;
  swap_total_mb: number;
  swap_used_mb: number;
  swap_used_pct: number;
}

export interface DiskEntry {
  drive: string;
  total_gb: number;
  free_gb: number;
}

export interface NetworkEntry {
  interface: string;
  address: string;
}

export interface BatteryInfo {
  percent: number;
  plugged_in: boolean;
}

export interface GpuInfo {
  temperature_c: number | null;
  fans_rpm: Record<string, number>;
}

export interface MotherboardEntry {
  manufacturer: string;
  product: string;
  serial: string;
}

export interface MonitorData {
  system: SystemInfo;
  cpu: CpuInfo;
  memory: MemoryInfo;
  disk: DiskEntry[];
  network: NetworkEntry[];
  battery: BatteryInfo | null;
  gpu: GpuInfo;
  motherboard: MotherboardEntry[];
}
