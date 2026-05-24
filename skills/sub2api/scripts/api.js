/**
 * Generic API caller for Sub2API
 * Usage: <runtime> api.js <METHOD> <PATH> [JSON_BODY]
 *
 * Runs on: node (>=18), bun, deno
 * Zero dependencies — native fetch + JSON only
 */

const { BASE_URL, ACCESS_TOKEN, USER_ID } = require("./env");
const { sanitize } = require("./sanitize");

// --- Args ---

const args = process.argv.slice(2);
const method = args[0];
const urlPath = args[1];
const body = args[2] || null;

if (!method || !urlPath) {
  console.error("Usage: api.js <METHOD> <PATH> [JSON_BODY]");
  process.exit(1);
}

// --- Token key masking ---

function maskTokenKey(value) {
  if (typeof value !== "string") return value;
  const raw = value.startsWith("sk-") ? value.slice(3) : value;
  if (!raw) return value;
  if (raw.length <= 4) return "*".repeat(raw.length);
  if (raw.length <= 8) return raw.slice(0, 2) + "****" + raw.slice(-2);
  return raw.slice(0, 4) + "**********" + raw.slice(-4);
}

function walk(node) {
  if (Array.isArray(node)) return node.map(walk);
  if (node !== null && typeof node === "object") {
    const masked = {};
    for (const [k, v] of Object.entries(node)) {
      masked[k] =
        (k === "key" || k === "access_token" || k === "session_token" || k === "id_token") && typeof v === "string"
          ? maskTokenKey(v) : walk(v);
    }
    return masked;
  }
  return node;
}

function shouldMask(urlPath) {
  return urlPath.startsWith("/api/v1/admin/api-keys") || urlPath.startsWith("/api/v1/auth/");
}

// --- Main ---

async function main() {
  const fetchOptions = {
    method,
    headers: {
      Authorization: `Bearer ${ACCESS_TOKEN}`,
      "Content-Type": "application/json",
    },
  };

  if (USER_ID) {
    fetchOptions.headers["X-User-Id"] = USER_ID;
  }

  if (body) {
    fetchOptions.body = body;
  }

  const res = await fetch(`${BASE_URL}${urlPath}`, fetchOptions);
  const text = await res.text();

  if (res.status >= 400) {
    console.error(`HTTP ${res.status} Error:`);
    try {
      const err = JSON.parse(text);
      console.error(err.message || JSON.stringify(err));
    } catch {
      console.error(text);
    }
    process.exit(1);
  }

  if (shouldMask(urlPath)) {
    try {
      const data = JSON.parse(text);
      console.log(sanitize(JSON.stringify(walk(data))));
    } catch {
      console.log(
        '{"success":false,"message":"sensitive response omitted because masking failed"}'
      );
    }

    if (method === "POST" && urlPath.includes("/api-keys")) {
      console.log(
        "\n[NEXT_STEP] Token created. Copy the `key` value from the response above and provide it to the user. Do NOT retrieve the key again."
      );
    }
  } else {
    console.log(text);
  }
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
