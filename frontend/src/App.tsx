import { useEffect, useRef, useState, useCallback } from "react";
import type { MonitorData, CpuInfo, MemoryInfo, DiskEntry, GpuInfo, BatteryInfo } from "./types";

const DEFAULT_WS_URL = "ws://localhost:8765";
const LS_KEY = "pymonitor_ws_url";

type ConnStatus = "connecting" | "connected" | "disconnected";

// ── WebSocket hook ────────────────────────────────────────────────────────────

function useMonitorSocket() {
  const [url, setUrl] = useState<string>(
    () => localStorage.getItem(LS_KEY) ?? DEFAULT_WS_URL
  );
  const [data, setData] = useState<MonitorData | null>(null);
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const [sourceConnected, setSourceConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // fresh=true clears stale data (used when URL changes); false keeps last
  // known data visible while retrying (fixes the black-screen flicker)
  const connect = useCallback((targetUrl: string, fresh: boolean) => {
    if (retryRef.current) clearTimeout(retryRef.current);
    wsRef.current?.close();
    setStatus("connecting");
    if (fresh) {
      setData(null);
      setSourceConnected(false);
    }

    const ws = new WebSocket(targetUrl);
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg?.type === "source_disconnected") {
          setSourceConnected(false);
          return;
        }
        setData(msg as MonitorData);
        setSourceConnected(true);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => setStatus("disconnected");

    ws.onclose = () => {
      setStatus("disconnected");
      // retry without clearing data — avoid black flash
      retryRef.current = setTimeout(() => connect(targetUrl, false), 3000);
    };
  }, []);

  useEffect(() => {
    connect(url, true);
    return () => {
      wsRef.current?.close();
      if (retryRef.current) clearTimeout(retryRef.current);
    };
  }, [url, connect]);

  const changeUrl = useCallback((newUrl: string) => {
    localStorage.setItem(LS_KEY, newUrl);
    setUrl(newUrl);
  }, []);

  return { data, status, sourceConnected, lastUpdated, url, changeUrl };
}

// ── URL editor in header ──────────────────────────────────────────────────────

function UrlEditor({
  url,
  status,
  onChange,
}: {
  url: string;
  status: ConnStatus;
  onChange: (u: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(url);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit() {
    setDraft(url);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== url) onChange(trimmed);
    setEditing(false);
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") setEditing(false);
  }

  const dotClass = status === "connected" ? "connected" : status === "connecting" ? "connecting" : "disconnected";

  return (
    <div className="url-editor">
      <div className={`status-dot ${dotClass}`} style={{ flexShrink: 0 }} />
      {editing ? (
        <input
          ref={inputRef}
          className="url-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={onKey}
          spellCheck={false}
        />
      ) : (
        <button className="url-display" onClick={startEdit} title="Click to change backend URL">
          {url}
          <span className="url-edit-hint">✎</span>
        </button>
      )}
    </div>
  );
}

// ── Small primitives ──────────────────────────────────────────────────────────

function Bar({ pct }: { pct: number }) {
  const color =
    pct > 85 ? "var(--red)" : pct > 65 ? "var(--yellow)" : "var(--green)";
  return (
    <div className="bar-track">
      <div
        className="bar-fill"
        style={{ width: `${Math.min(pct, 100)}%`, background: color }}
      />
    </div>
  );
}

function BarRow({ label, pct, sub }: { label: string; pct: number; sub: string }) {
  return (
    <div className="bar-wrap">
      <div className="bar-label-row">
        <span className="label">{label}</span>
        <span className="value">{sub}</span>
      </div>
      <Bar pct={pct} />
    </div>
  );
}

function TempDisplay({ temp }: { temp: number | null }) {
  if (temp === null) return <span className="temp na">N/A</span>;
  const cls = temp > 80 ? "hot" : temp > 65 ? "warm" : "cool";
  return <span className={`temp ${cls}`}>{temp.toFixed(1)} °C</span>;
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-box">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

function FanList({ fans }: { fans: Record<string, number> }) {
  const entries = Object.entries(fans);
  if (entries.length === 0) return null;
  return (
    <>
      {entries.map(([name, rpm]) => (
        <div className="fan-entry" key={name}>
          <span className="fan-name">{name}</span>
          <span className="fan-rpm">{rpm.toLocaleString()} RPM</span>
        </div>
      ))}
    </>
  );
}

function CorePct({ pct }: { pct: number }) {
  const color = pct > 85 ? "var(--red)" : pct > 65 ? "var(--yellow)" : "var(--green)";
  return <span style={{ color }}>{pct.toFixed(0)}%</span>;
}

// ── Cards ─────────────────────────────────────────────────────────────────────

function CardShell({
  icon, title, children, scroll,
}: {
  icon: string; title: string; children: React.ReactNode; scroll?: boolean;
}) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="icon">{icon}</span>
        {title}
      </div>
      <div className={`card-body${scroll ? " scroll" : ""}`}>{children}</div>
    </div>
  );
}

function SystemCard({ data }: { data: MonitorData }) {
  const s = data.system;
  return (
    <CardShell icon="🖥" title="System">
      <div className="row"><span className="label">Hostname</span><span className="value">{s.hostname}</span></div>
      <div className="row"><span className="label">User</span><span className="value">{s.user}</span></div>
      <div className="row"><span className="label">Platform</span><span className="value">{s.platform}</span></div>
      <div className="row"><span className="label">Boot Time</span><span className="value">{s.boot_time}</span></div>
    </CardShell>
  );
}

function CpuCard({ cpu }: { cpu: CpuInfo }) {
  return (
    <CardShell icon="⚡" title="CPU">
      <div className="row" style={{ alignItems: "flex-start" }}>
        <TempDisplay temp={cpu.temperature_c} />
        <div className="stat-grid" style={{ flex: 1, marginLeft: 12 }}>
          <StatBox label="Physical" value={String(cpu.physical_cores)} />
          <StatBox label="Logical" value={String(cpu.total_cores)} />
          <StatBox label="Current" value={cpu.current_freq_mhz ? `${cpu.current_freq_mhz.toFixed(0)} MHz` : "N/A"} />
          <StatBox label="Max" value={cpu.max_freq_mhz ? `${cpu.max_freq_mhz.toFixed(0)} MHz` : "N/A"} />
        </div>
      </div>
      <BarRow label="Total Usage" pct={cpu.total_usage_pct} sub={`${cpu.total_usage_pct.toFixed(1)}%`} />
      <div className="divider" />
      <div className="core-grid">
        {cpu.per_core_usage_pct.map((pct, i) => (
          <div className="core-cell" key={i}>
            <div className="core-id">C{i}</div>
            <div className="core-pct"><CorePct pct={pct} /></div>
          </div>
        ))}
      </div>
      <FanList fans={cpu.fans_rpm} />
    </CardShell>
  );
}

function MemoryCard({ mem }: { mem: MemoryInfo }) {
  const totalGb = (mem.total_mb / 1024).toFixed(1);
  const usedGb = (mem.used_mb / 1024).toFixed(1);
  const swapTotalGb = (mem.swap_total_mb / 1024).toFixed(1);
  const swapUsedGb = (mem.swap_used_mb / 1024).toFixed(1);
  return (
    <CardShell icon="🧠" title="Memory">
      <BarRow label="RAM" pct={mem.used_pct} sub={`${usedGb} / ${totalGb} GB (${mem.used_pct.toFixed(1)}%)`} />
      <BarRow label="Swap" pct={mem.swap_used_pct} sub={`${swapUsedGb} / ${swapTotalGb} GB (${mem.swap_used_pct.toFixed(1)}%)`} />
      <div className="stat-grid">
        <StatBox label="Total RAM" value={`${totalGb} GB`} />
        <StatBox label="Available" value={`${(mem.available_mb / 1024).toFixed(1)} GB`} />
        <StatBox label="Used" value={`${usedGb} GB`} />
        <StatBox label="Swap Used" value={`${swapUsedGb} GB`} />
      </div>
    </CardShell>
  );
}

function GpuCard({ gpu }: { gpu: GpuInfo }) {
  return (
    <CardShell icon="🎮" title="GPU">
      <div className="row">
        <span className="label">Temperature</span>
        <TempDisplay temp={gpu.temperature_c} />
      </div>
      <FanList fans={gpu.fans_rpm} />
      {Object.keys(gpu.fans_rpm).length === 0 && <span className="label">Fan speed unavailable</span>}
    </CardShell>
  );
}

function DiskCard({ disks }: { disks: DiskEntry[] }) {
  return (
    <CardShell icon="💾" title="Disks" scroll={disks.length > 3}>
      {disks.map((d) => {
        const usedGb = d.total_gb - d.free_gb;
        const pct = d.total_gb > 0 ? (usedGb / d.total_gb) * 100 : 0;
        return (
          <div className="disk-entry" key={d.drive}>
            <BarRow label={d.drive} pct={pct} sub={`${usedGb} / ${d.total_gb} GB`} />
          </div>
        );
      })}
    </CardShell>
  );
}

function NetworkCard({ network }: { network: MonitorData["network"] }) {
  return (
    <CardShell icon="🌐" title="Network" scroll={network.length > 6}>
      {network.map((n, i) => (
        <div className="net-entry" key={i}>
          <div className="net-iface">{n.interface}</div>
          <div className="net-addr">{n.address}</div>
        </div>
      ))}
    </CardShell>
  );
}

function BatteryCard({ battery }: { battery: BatteryInfo }) {
  const color = battery.percent < 20 ? "var(--red)" : battery.percent < 50 ? "var(--yellow)" : "var(--green)";
  return (
    <CardShell icon="🔋" title="Battery">
      <div className="battery-pct" style={{ color }}>{battery.percent.toFixed(0)}%</div>
      <Bar pct={battery.percent} />
      <div className="row" style={{ marginTop: 4 }}>
        <span className="label">Status</span>
        <span className="value">{battery.plugged_in ? "⚡ Charging" : "🔋 On Battery"}</span>
      </div>
    </CardShell>
  );
}

function MotherboardCard({ boards }: { boards: MonitorData["motherboard"] }) {
  if (boards.length === 0) return null;
  const b = boards[0];
  return (
    <CardShell icon="🔩" title="Motherboard">
      <div className="row"><span className="label">Manufacturer</span><span className="value">{b.manufacturer}</span></div>
      <div className="row"><span className="label">Product</span><span className="value">{b.product}</span></div>
      <div className="row">
        <span className="label">Serial</span>
        <span className="value" style={{ color: "var(--muted)", fontSize: 11 }}>{b.serial}</span>
      </div>
    </CardShell>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function App() {
  const { data, status, sourceConnected, lastUpdated, url, changeUrl } = useMonitorSocket();

  const appDisconnected = status === "connected" && !sourceConnected && data !== null;

  return (
    <>
      <header className="header">
        <h1><span>Py</span>Monitor</h1>
        <UrlEditor url={url} status={status} onChange={changeUrl} />
        <div className="header-meta">
          {lastUpdated && <span>Updated {lastUpdated}</span>}
        </div>
      </header>

      {appDisconnected && (
        <div className="stale-banner">
          Desktop app disconnected — showing last known data
        </div>
      )}

      {!data ? (
        <div className="placeholder">
          <div className="placeholder-icon">📡</div>
          <p>{status === "connecting" ? "Connecting to backend…" : "No data — is the desktop app running?"}</p>
          <p style={{ fontSize: 11, opacity: 0.6 }}>cd app &amp;&amp; python app.py</p>
        </div>
      ) : (
        <main className={`dashboard${appDisconnected ? " stale" : ""}`}>
          <SystemCard data={data} />
          <CpuCard cpu={data.cpu} />
          <MemoryCard mem={data.memory} />
          <GpuCard gpu={data.gpu} />
          {data.disk.length > 0 && <DiskCard disks={data.disk} />}
          {data.network.length > 0 && <NetworkCard network={data.network} />}
          {data.battery && <BatteryCard battery={data.battery} />}
          {data.motherboard.length > 0 && <MotherboardCard boards={data.motherboard} />}
        </main>
      )}
    </>
  );
}
