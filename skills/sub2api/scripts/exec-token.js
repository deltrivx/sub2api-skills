/**
 * Execute command with token key securely substituted.
 * Usage: <runtime> exec-token.js <token_id> -- <command with __SUB2API_TOKEN_<id>__>
 */

const { BASE_URL, ACCESS_TOKEN } = require("./env");
const { sanitize } = require("./sanitize");
const { spawn } = require("child_process");

const args = process.argv.slice(2);
const dashIdx = args.indexOf("--");

if (dashIdx < 1) {
  console.error("Usage: exec-token.js <token_id> -- <command with __SUB2API_TOKEN_<id>__>");
  process.exit(1);
}

const tokenId = args[0];
const commandParts = args.slice(dashIdx + 1);
const command = commandParts.join(" ");

async function main() {
  const res = await fetch(`${BASE_URL}/api/v1/admin/api-keys/${tokenId}`, {
    headers: { Authorization: `Bearer ${ACCESS_TOKEN}` },
  });

  if (!res.ok) {
    console.error(`HTTP ${res.status}: failed to fetch token ${tokenId}`);
    process.exit(1);
  }

  const data = await res.json();
  const key = data?.data?.key;

  if (!key) {
    console.error("No key found in response");
    process.exit(1);
  }

  const placeholder = `__SUB2API_TOKEN_${tokenId}__`;
  const resolved = command.replace(new RegExp(placeholder, "g"), key);

  // Execute the resolved command
  const child = spawn("/bin/sh", ["-c", resolved], {
    stdio: ["inherit", "pipe", "pipe"],
    env: { ...process.env, SUB2API_KEY: key },
  });

  let stdout = "";
  let stderr = "";

  child.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });

  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  child.on("close", (code) => {
    // Print sanitized output
    if (stdout) console.log(sanitize(stdout));
    if (stderr) process.stderr.write(sanitize(stderr));
    process.exit(code || 0);
  });
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
