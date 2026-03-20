import { importPKCS8, SignJWT } from "jose";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const USER_AGENT = "profile-webhook-worker";

const ALLOWED_EVENTS = {
  push: null,                    // commits (no action field)
  repository: null,              // created, edited, renamed, privatized, publicized, archived, deleted
  pull_request: new Set(["opened", "closed", "reopened"]),
  pull_request_review: null,     // all actions
  star: null,                    // created, deleted (no action filtering needed)
  fork: null,                    // fork events (no action field)
  issues: new Set(["opened", "closed"]),
};

// GitHub App keys are PKCS#1 (BEGIN RSA PRIVATE KEY), but jose needs PKCS#8.
// Convert by wrapping the PKCS#1 DER in a PKCS#8 ASN.1 envelope.
function ensurePKCS8(pem) {
  pem = pem.replace(/\\n/g, "\n");
  if (!pem.includes("BEGIN RSA PRIVATE KEY")) return pem;

  const b64 = pem
    .replace(/-----BEGIN RSA PRIVATE KEY-----/, "")
    .replace(/-----END RSA PRIVATE KEY-----/, "")
    .replace(/\\n/g, "")
    .replace(/\s/g, "");
  const pkcs1 = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));

  // PKCS#8 = SEQUENCE { version INTEGER 0, AlgorithmIdentifier, OCTET STRING { pkcs1 } }
  const algorithmId = new Uint8Array([
    0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01,
    0x01, 0x05, 0x00,
  ]);
  const version = new Uint8Array([0x02, 0x01, 0x00]);
  const octet = asn1Wrap(0x04, pkcs1);
  const pkcs8 = asn1Wrap(0x30, concat(version, algorithmId, octet));

  const lines = btoa(String.fromCharCode(...pkcs8)).match(/.{1,64}/g);
  return `-----BEGIN PRIVATE KEY-----\n${lines.join("\n")}\n-----END PRIVATE KEY-----`;
}

function asn1Wrap(tag, content) {
  const len =
    content.length < 0x80
      ? [content.length]
      : content.length < 0x100
        ? [0x81, content.length]
        : [0x82, (content.length >> 8) & 0xff, content.length & 0xff];
  const out = new Uint8Array(1 + len.length + content.length);
  out[0] = tag;
  out.set(len, 1);
  out.set(content, 1 + len.length);
  return out;
}

function concat(...arrays) {
  const total = arrays.reduce((s, a) => s + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

async function generateJWT(env) {
  const privateKey = await importPKCS8(ensurePKCS8(env.APP_PRIVATE_KEY), "RS256");
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({})
    .setProtectedHeader({ alg: "RS256" })
    .setIssuer(env.APP_ID)
    .setIssuedAt(now - 60)
    .setExpirationTime(now + 600)
    .sign(privateKey);
}

async function getInstallationToken(env) {
  const jwt = await generateJWT(env);

  let installationId = env.INSTALLATION_ID;
  if (!installationId) {
    const res = await fetch("https://api.github.com/app/installations", {
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": USER_AGENT,
      },
    });
    const installations = await res.json();
    installationId = installations[0].id;
  }

  const res = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": USER_AGENT,
      },
    },
  );
  const data = await res.json();
  return data.token;
}

// ---------------------------------------------------------------------------
// Signature verification
// ---------------------------------------------------------------------------

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

async function verifySignature(secret, body, signatureHeader) {
  if (!signatureHeader || !signatureHeader.startsWith("sha256=")) {
    return false;
  }
  const receivedHex = signatureHeader.slice("sha256=".length);
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signed = await crypto.subtle.sign("HMAC", key, encoder.encode(body));
  const expected = new Uint8Array(signed);
  const received = hexToBytes(receivedHex);

  if (expected.byteLength !== received.byteLength) {
    return false;
  }
  return crypto.subtle.timingSafeEqual(expected, received);
}

// ---------------------------------------------------------------------------
// Worker
// ---------------------------------------------------------------------------

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    try {
      const rawBody = await request.text();

      const valid = await verifySignature(
        env.WEBHOOK_SECRET,
        rawBody,
        request.headers.get("X-Hub-Signature-256"),
      );
      if (!valid) {
        return new Response("Unauthorized", { status: 401 });
      }

      const payload = JSON.parse(rawBody);
      const event = request.headers.get("X-GitHub-Event");

      const allowedActions = ALLOWED_EVENTS[event];
      if (allowedActions === undefined) {
        // Event not in allowlist — acknowledge but ignore
        return new Response("OK", { status: 200 });
      }

      // allowedActions is null (all actions) or a Set of specific actions
      if (allowedActions !== null && !allowedActions.has(payload.action)) {
        return new Response("OK", { status: 200 });
      }

      // Forward to Durable Object for debounce + rate limit
      const id = env.DEBOUNCER.idFromName("singleton");
      const stub = env.DEBOUNCER.get(id);
      const doResponse = await stub.fetch(
        new Request("https://do/event", {
          method: "POST",
          headers: {
            "X-GitHub-Delivery": request.headers.get("X-GitHub-Delivery") || "",
          },
          body: rawBody,
        }),
      );

      const result = await doResponse.json();
      return Response.json(result, { status: 200 });
    } catch (err) {
      console.error("Webhook handler error:", err.message);
      return new Response("Internal Server Error", { status: 500 });
    }
  },

  async scheduled(event, env, ctx) {
    const repo = env.DISPATCH_REPO;
    if (!repo || !repo.includes("/")) {
      console.error("DISPATCH_REPO not set or invalid (expected 'owner/repo')");
      return;
    }
    try {
      const token = await getInstallationToken(env);
      await fetch(
        `https://api.github.com/repos/${repo}/actions/workflows/update-profile.yml/dispatches`,
        {
          method: "POST",
          headers: {
            Authorization: `token ${token}`,
            Accept: "application/vnd.github+json",
            "User-Agent": USER_AGENT,
          },
          body: JSON.stringify({ ref: "main" }),
        },
      );
    } catch (err) {
      console.error("Scheduled dispatch error:", err.message);
    }
  },
};

// ---------------------------------------------------------------------------
// Durable Object — ProfileDebounce
// ---------------------------------------------------------------------------

export class ProfileDebounce {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.sql = ctx.storage.sql;
    this.#ensureTables();
  }

  #ensureTables() {
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS deliveries (
        id TEXT PRIMARY KEY,
        created_at INTEGER
      )
    `);
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS dispatches (
        timestamp INTEGER
      )
    `);
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY,
        value TEXT
      )
    `);
  }

  async fetch(request) {
    const deliveryId = request.headers.get("X-GitHub-Delivery") || "";
    const now = Date.now();

    // Replay protection — reject duplicate delivery IDs (5-min TTL)
    if (deliveryId) {
      const existing = this.sql
        .exec("SELECT id FROM deliveries WHERE id = ?", deliveryId)
        .toArray();
      if (existing.length > 0) {
        return Response.json({ dispatched: false, reason: "duplicate" });
      }
      this.sql.exec(
        "INSERT INTO deliveries (id, created_at) VALUES (?, ?)",
        deliveryId,
        now,
      );
    }

    // Clean expired delivery IDs (older than 5 minutes)
    const fiveMinAgo = now - 5 * 60 * 1000;
    this.sql.exec("DELETE FROM deliveries WHERE created_at < ?", fiveMinAgo);

    // Hourly rate limit — max 30 dispatches per hour
    const oneHourAgo = now - 60 * 60 * 1000;
    const countResult = this.sql
      .exec("SELECT COUNT(*) as cnt FROM dispatches WHERE timestamp > ?", oneHourAgo)
      .toArray();
    const hourlyCount = countResult[0].cnt;
    if (hourlyCount >= 30) {
      return Response.json({ dispatched: false, reason: "rate_limited" });
    }

    // First-event-wins debounce: set alarm only if none pending
    const pending = this.sql
      .exec("SELECT value FROM state WHERE key = 'alarm_pending'")
      .toArray();
    if (pending.length === 0 || pending[0].value !== "true") {
      this.sql.exec(
        "INSERT OR REPLACE INTO state (key, value) VALUES ('alarm_pending', 'true')",
      );
      await this.ctx.storage.setAlarm(Date.now() + 60_000);
    }

    return Response.json({ dispatched: true });
  }

  async alarm() {
    const repo = this.env.DISPATCH_REPO;
    if (!repo || !repo.includes("/")) {
      console.error("DISPATCH_REPO not set or invalid (expected 'owner/repo')");
      this.sql.exec("DELETE FROM state WHERE key = 'alarm_pending'");
      return;
    }
    try {
      const token = await getInstallationToken(this.env);
      const res = await fetch(
        `https://api.github.com/repos/${repo}/dispatches`,
        {
          method: "POST",
          headers: {
            Authorization: `token ${token}`,
            Accept: "application/vnd.github+json",
            "User-Agent": USER_AGENT,
          },
          body: JSON.stringify({ event_type: "profile-update" }),
        },
      );
      if (!res.ok) {
        const body = await res.text();
        console.error(`Dispatch failed: HTTP ${res.status} — ${body}`);
      }

      // Record dispatch
      this.sql.exec(
        "INSERT INTO dispatches (timestamp) VALUES (?)",
        Date.now(),
      );
    } catch (err) {
      console.error("Alarm dispatch error:", err.message);
    }

    // Clean up records older than 24 hours
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
    this.sql.exec("DELETE FROM deliveries WHERE created_at < ?", oneDayAgo);
    this.sql.exec("DELETE FROM dispatches WHERE timestamp < ?", oneDayAgo);

    // Clear pending flag
    this.sql.exec("DELETE FROM state WHERE key = 'alarm_pending'");
  }
}
