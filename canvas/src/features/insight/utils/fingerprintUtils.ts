// features/insight/utils/fingerprintUtils.ts
// KPI fingerprint parsing and URL parameter utilities

/**
 * Parse a KPI fingerprint from URL search params.
 * The fingerprint may be URL-encoded; this handles decoding.
 */
export function parseFingerprint(fp: string): string {
  try {
    return decodeURIComponent(fp).trim();
  } catch {
    return fp.trim();
  }
}

/**
 * Extract fingerprint from URLSearchParams.
 * Returns null if not present.
 */
export function getFingerprintFromParams(
  searchParams: URLSearchParams,
): string | null {
  const fp = searchParams.get('fp');
  if (!fp) return null;
  return parseFingerprint(fp);
}

/**
 * Build URL search string with fingerprint parameter.
 */
export function buildFingerprintUrl(
  basePath: string,
  fingerprint: string,
): string {
  const encoded = encodeURIComponent(fingerprint);
  return `${basePath}?fp=${encoded}`;
}

/**
 * Generate a simple display name from a fingerprint-like string.
 * e.g. "orders_pending_count" -> "Orders Pending Count"
 */
export function fingerprintToDisplayName(fp: string): string {
  // Strip sha256: prefix if present
  const cleaned = fp.replace(/^sha256:[a-f0-9]+$/, fp);
  if (cleaned.startsWith('sha256:')) {
    return fp; // it's a hash, no pretty name
  }
  return cleaned
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
