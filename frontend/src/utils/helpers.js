/**
 * Parses a GitHub PR URL and extracts owner, repo, and PR number.
 * @param {string} url
 * @returns {{ owner: string, repo: string, prNumber: number } | null}
 */
export function parseGitHubPRUrl(url) {
  if (!url || typeof url !== 'string') return null;
  const trimmed = url.trim();
  const pattern = /^https?:\/\/github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)\/pull\/(\d+)\/?$/;
  const match = trimmed.match(pattern);
  if (!match) return null;
  return {
    owner: match[1],
    repo: match[2],
    prNumber: parseInt(match[3], 10),
  };
}

/**
 * Returns an overall risk label based on conflicts.
 */
export function computeOverallRisk(conflicts) {
  if (!conflicts || conflicts.length === 0) return 'No Conflicts';
  const hasHigh = conflicts.some((c) => c.risk === 'High');
  if (hasHigh) return 'High Risk';
  const hasMedium = conflicts.some((c) => c.risk === 'Medium');
  if (hasMedium) return 'Medium Risk';
  return 'Low Risk';
}

/**
 * Returns a human-readable relative time string.
 */
export function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
