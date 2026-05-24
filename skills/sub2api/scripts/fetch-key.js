/**
 * Shared token key fetcher for Sub2API scripts.
 *
 * Fetches the full key from GET /api/v1/admin/api-keys/{id}.
 * The key is returned in memory only — never logged or printed.
 *
 * @param {string|number} tokenId
 * @param {{ baseUrl: string, accessToken: string }} config
 * @returns {Promise<string>} full key value
 */
async function fetchTokenKey(tokenId, { baseUrl, accessToken }) {
  const res = await fetch(`${baseUrl}/api/v1/admin/api-keys/${tokenId}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (res.status >= 400) {
    const errText = await res.text();
    let msg = `HTTP ${res.status}`;
    try {
      const errJson = JSON.parse(errText);
      if (errJson.message) msg = errJson.message;
    } catch {}
    throw new Error(msg);
  }

  const body = await res.json();
  const key = body?.data?.key;
  if (!key) {
    throw new Error("API response did not contain a key");
  }

  return key;
}

module.exports = { fetchTokenKey };
