/**
 * Inject key script for Sub2API
 * Usage: <runtime> inject-key.js --scan <file_path>
 *        <runtime> inject-key.js <token_id> <file_path>
 *
 * --scan: reads a config file and prints its structure with secrets redacted
 * <token_id> <file_path>: replaces __SUB2API_TOKEN_<id>__ placeholder with the real key
 */

const { BASE_URL, ACCESS_TOKEN, USER_ID } = require("./env");
const { sanitize } = require("./sanitize");
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);

// --- Scan mode ---
if (args[0] === "--scan") {
  const filePath = args[1];
  if (!filePath) {
    console.error("Usage: inject-key.js --scan <file_path>");
    process.exit(1);
  }
  if (!fs.existsSync(filePath)) {
    console.error("File not found:", filePath);
    process.exit(1);
  }

  const content = fs.readFileSync(filePath, "utf-8");
  const redacted = content
    .replace(/(sk-[A-Za-z0-9]{8,})/g, "sk-***REDACTED***")
    .replace(/(["'])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}["']/g, '"***JWT_REDACTED***"')
    .replace(/(access_token|session_token|id_token|password|secret)\s*[:=]\s*["'][^"']{4,}["']/gi, "$1: ***REDACTED***");

  console.log("--- Config scan: " + filePath + " ---");
  console.log(redacted);
  process.exit(0);
}

// --- Inject mode ---
const tokenId = args[0];
const filePath = args[1];

if (!tokenId || !filePath) {
  console.error("Usage: inject-key.js <token_id> <file_path>");
  console.error("       inject-key.js --scan <file_path>");
  process.exit(1);
}

if (!fs.existsSync(filePath)) {
  console.error("File not found:", filePath);
  process.exit(1);
}

async function main() {
  const res = await fetch(`${BASE_URL}/api/v1/admin/api-keys/${tokenId}`, {
    headers: { Authorization: `Bearer ${ACCESS_TOKEN}` },
  });

  if (!res.ok) {
    console.error(`Failed to fetch token ${tokenId}: HTTP ${res.status}`);
    process.exit(1);
  }

  const data = await res.json();
  const key = data?.data?.key;
  if (!key) {
    console.error("No key found in response");
    process.exit(1);
  }

  const placeholder = `__SUB2API_TOKEN_${tokenId}__`;
  let content = fs.readFileSync(filePath, "utf-8");

  if (!content.includes(placeholder)) {
    console.error(`Placeholder '${placeholder}' not found in ${filePath}`);
    console.error("Use --scan first to inspect the file, then add the placeholder.");
    process.exit(1);
  }

  content = content.replace(new RegExp(placeholder, "g"), key);
  
  // Atomic write: write to temp then rename
  const tmpPath = filePath + ".tmp." + Date.now();
  fs.writeFileSync(tmpPath, content, "utf-8");
  fs.renameSync(tmpPath, filePath);

  console.log(`Token ${tokenId} applied to ${filePath}`);
  console.log("Key was injected and will NOT be displayed.");
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
