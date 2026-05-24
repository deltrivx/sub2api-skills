/**
 * Copy key to clipboard — never prints the key value.
 * Usage: <runtime> copy-key.js <token_id>
 */

const { BASE_URL, ACCESS_TOKEN } = require("./env");
const { sanitize } = require("./sanitize");
const { spawn } = require("child_process");

const tokenId = process.argv[2];
if (!tokenId) {
  console.error("Usage: copy-key.js <token_id>");
  process.exit(1);
}

function clip(value) {
  return new Promise((resolve, reject) => {
    let cmd, args;
    if (process.platform === "darwin") {
      cmd = "pbcopy";
      args = [];
    } else if (process.platform === "linux") {
      if (process.env.WAYLAND_DISPLAY) {
        cmd = "wl-copy";
        args = [];
      } else {
        cmd = "xclip";
        args = ["-selection", "clipboard"];
      }
    } else {
      reject(new Error("Unsupported platform for clipboard"));
      return;
    }
    const proc = spawn(cmd, args);
    proc.stdin.write(value);
    proc.stdin.end();
    proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`Clipboard exit code ${code}`))));
  });
}

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

  try {
    await clip(key);
    console.log(`Token ${tokenId} copied to clipboard.`);
    console.log("The key value was NOT printed and is NOT in the conversation.");
  } catch (err) {
    if (err.message.includes("Unsupported platform")) {
      console.error("This terminal does not support clipboard operations.");
      console.error("Try using /sub2api apply-token or /sub2api exec-token instead.");
    } else {
      console.error("Clipboard error:", err.message);
    }
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
