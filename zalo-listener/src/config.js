/**
 * JAMA Zalo Listener -- Environment Configuration
 *
 * All settings are loaded from environment variables with sensible defaults.
 * ZALO_INGEST_SECRET is mandatory; the service exits immediately if it is missing.
 */

import "dotenv/config";

const REQUIRED_VARS = ["ZALO_INGEST_SECRET"];

// Validate mandatory variables at import time.
for (const v of REQUIRED_VARS) {
  if (!process.env[v]) {
    console.error(`[FATAL] Missing required env var: ${v}`);
    process.exit(1);
  }
}

export const config = Object.freeze({
  /** Backend base URL, no trailing slash. */
  backendUrl: (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/+$/, ""),

  /** Shared secret sent as X-Zalo-Secret header. */
  secret: process.env.ZALO_INGEST_SECRET,

  /** Poll interval for pending-login requests (ms). */
  pollMs: Math.max(3000, Number(process.env.POLL_MS || 10_000)),

  /** Heartbeat interval (ms). */
  heartbeatMs: Math.max(10_000, Number(process.env.HEARTBEAT_MS || 60_000)),

  /** Winston log level. */
  logLevel: process.env.LOG_LEVEL || "info",
});
