/** Review bins. Real labels load after unlock from GET /api/test/review-bins. */

export const REVIEW_BINS = [];

export function setReviewBins(list) {
  if (!Array.isArray(list)) return;
  REVIEW_BINS.splice(0, REVIEW_BINS.length, ...list);
}

export function binsForPreset(presetId) {
  return REVIEW_BINS.filter((b) => b.presetId === presetId && !b.unfiled);
}
