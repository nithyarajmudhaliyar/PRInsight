/**
 * PRInsight API service — communicates with the FastAPI backend.
 *
 * @module services/api
 */

const API_BASE_URL = 'http://127.0.0.1:8000';

/**
 * Analyze a GitHub Pull Request for merge conflicts.
 *
 * Calls POST /api/v1/analyze on the backend and returns
 * the response data in a normalized shape that components
 * can consume directly.
 *
 * @param {{ owner: string, repo: string, prNumber: number }} params
 * @returns {Promise<object>} Normalized analysis result
 * @throws {Error} With a user-friendly message for every failure mode
 */
export async function analyzePR({ owner, repo, prNumber }) {
  const pr_url = `https://github.com/${owner}/${repo}/pull/${prNumber}`;

  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pr_url }),
    });
  } catch (networkError) {
    // fetch() itself threw — network is down or backend unreachable
    throw new Error(
      'Unable to reach the PRInsight server. Make sure the backend is running on http://127.0.0.1:8000.'
    );
  }

  // Handle HTTP error responses with user-friendly messages
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const serverMessage = errorData?.error?.message;

    switch (response.status) {
      case 400:
        throw new Error(serverMessage || 'Invalid Pull Request URL format.');
      case 404:
        throw new Error(serverMessage || 'Repository or Pull Request not found.');
      case 422:
        throw new Error(serverMessage || 'Invalid request. Please check the URL and try again.');
      case 429:
        throw new Error(serverMessage || 'GitHub API rate limit exceeded. Please wait and try again.');
      default:
        throw new Error(serverMessage || `Unexpected server error (HTTP ${response.status}).`);
    }
  }

  const json = await response.json();

  // Normalize the backend response into the shape components expect.
  // The backend returns { status, data: { repository, pull_request, analysis, metadata } }
  return normalizeResponse(json.data);
}

/**
 * Transform the backend response into the shape the UI components consume.
 *
 * This adapter layer means backend schema changes only affect this function,
 * not every component across the app.
 */
function normalizeResponse(data) {
  const { repository, pull_request, analysis, metadata } = data;

  // Compute an overall risk label from the individual conflict risk levels
  const overallRisk = computeOverallRisk(analysis.conflicts);

  return {
    // Repository as "owner/repo" string for display
    repository: `${repository.owner}/${repository.repo}`,

    // Pull Request details
    pullRequest: {
      number: pull_request.number,
      title: pull_request.title,
      author: pull_request.author,
      url: pull_request.url,
      changedFiles: pull_request.changed_files,
      filesChanged: pull_request.changed_files.length,
    },

    // Analysis summary
    openPRsChecked: analysis.prs_analyzed,
    totalOpenPRs: analysis.total_open_prs,
    conflictsFound: analysis.conflicts_found,
    overallRisk,

    // Conflicts list — normalized for ConflictCard
    conflicts: analysis.conflicts.map((c, index) => ({
      id: index + 1,
      number: c.pr_number,
      title: c.pr_title,
      author: c.pr_author,
      risk: capitalizeFirst(c.risk_level),
      overlappingFiles: c.overlapping_files,
      overlapCount: c.overlap_count,
      url: c.pr_url,
    })),

    // Metadata for the footer section
    metadata: {
      analysisDurationMs: metadata.analysis_duration_ms,
      cacheHit: metadata.cache_hit,
      warning: metadata.warning || null,
      prsAnalyzed: metadata.prs_analyzed,
      totalOpenPRs: metadata.total_open_prs,
    },
  };
}

/**
 * Determine the highest risk level across all conflicts.
 * Returns a display-ready label matching RiskBadge's config keys.
 */
function computeOverallRisk(conflicts) {
  if (!conflicts || conflicts.length === 0) return 'No Conflicts';
  const levels = conflicts.map((c) => c.risk_level);
  if (levels.includes('high')) return 'High Risk';
  if (levels.includes('medium')) return 'Medium Risk';
  return 'Low Risk';
}

/**
 * Capitalize the first letter of a string (e.g. "high" → "High").
 */
function capitalizeFirst(str) {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1);
}
