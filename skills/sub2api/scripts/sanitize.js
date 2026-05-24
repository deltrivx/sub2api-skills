/**
 * Sanitizer — strips ANSI escape codes and other control sequences
 * from command output before it reaches the AI.
 *
 * Usage: sanitize(text)
 */

function sanitize(text) {
  if (typeof text !== "string") return text;
  return text
    // ANSI escape (color codes, cursor sequences, etc.)
    .replace(/\x1B\[[0-9;]*[a-zA-Z]/g, "")
    // Carriage returns
    .replace(/\r/g, "")
    // Backspace: remove preceding char
    .replace(/.\x08/g, "")
    // OSC sequences (e.g. tmux clipboard)
    .replace(/\x1B\][^\x1B]*(\x1B\\|\x07)/g, "")
    // Remove terminal DCS sequences
    .replace(/\x1BP[^\x1B]*\x1B\\/g, "")
    // Remove terminal SOS/PM/APC sequences
    .replace(/\x1B[X^_][^\x1B]*\x1B\\/g, "")
    // Trim trailing newlines
    .replace(/\n{3,}$/, "\n");
}

module.exports = { sanitize };
