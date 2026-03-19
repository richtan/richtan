import { importPKCS8, SignJWT } from "jose";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DISPATCH_REPO = "richtan/richtan";
const USER_AGENT = "profile-webhook-worker";

const ALLOWED_EVENTS = {
  repository: new Set(["created"]),
  pull_request: new Set(["opened", "closed", "reopened"]),
  pull_request_review: null, // null = all actions allowed
};

async function generateJWT(env) {
  const privateKey = await importPKCS8(env.APP_PRIVATE_KEY, "RS256");
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
    try {
      const token = await getInstallationToken(env);
      await fetch(
        `https://api.github.com/repos/${DISPATCH_REPO}/actions/workflows/update-profile.yml/dispatches`,
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
    try {
      const token = await getInstallationToken(this.env);
      await fetch(
        `https://api.github.com/repos/${DISPATCH_REPO}/dispatches`,
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
