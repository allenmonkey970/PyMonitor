import { WebSocketServer, WebSocket } from "ws";

const PORT = parseInt(process.env.PORT ?? "8765", 10);
const PING_INTERVAL_MS = 5000;
const PING_TIMEOUT_MS  = 3000;

const wss = new WebSocketServer({ port: PORT, host: "0.0.0.0" });
const clients = new Set<WebSocket>();
const alive = new Map<WebSocket, boolean>();

let sourceClient: WebSocket | null = null;
let lastPayload: string | null = null;

function handleSourceDisconnect() {
  sourceClient = null;
  lastPayload = null;
  const notice = JSON.stringify({ type: "source_disconnected" });
  for (const client of clients) {
    if (client.readyState === WebSocket.OPEN) client.send(notice);
  }
  console.log("Data source disconnected.");
}

// Heartbeat — ping every client; terminate any that don't pong back in time
const heartbeat = setInterval(() => {
  for (const ws of clients) {
    if (!alive.get(ws)) {
      console.log("Client timed out, terminating.");
      const wasSource = ws === sourceClient;
      ws.terminate();
      clients.delete(ws);
      alive.delete(ws);
      if (wasSource) handleSourceDisconnect();
      continue;
    }
    alive.set(ws, false);
    ws.ping();
  }
}, PING_INTERVAL_MS);

wss.on("close", () => clearInterval(heartbeat));

wss.on("connection", (ws) => {
  clients.add(ws);
  alive.set(ws, true);

  if (lastPayload) ws.send(lastPayload);

  ws.on("pong", () => alive.set(ws, true));

  ws.on("message", (raw) => {
    const payload = raw.toString();
    try {
      JSON.parse(payload);
    } catch {
      return;
    }

    sourceClient = ws;
    lastPayload = payload;

    for (const client of clients) {
      if (client !== ws && client.readyState === WebSocket.OPEN) {
        client.send(payload);
      }
    }
  });

  ws.on("close", () => {
    const wasSource = ws === sourceClient;
    clients.delete(ws);
    alive.delete(ws);
    if (wasSource) handleSourceDisconnect();
  });

  ws.on("error", () => {
    const wasSource = ws === sourceClient;
    clients.delete(ws);
    alive.delete(ws);
    if (wasSource) handleSourceDisconnect();
  });
});

console.log(`PyMonitor relay running on ws://0.0.0.0:${PORT}`);
console.log("Waiting for the desktop app to connect and push metrics...");
