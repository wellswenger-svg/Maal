import { useCallback, useEffect, useState } from "react";
import { getTestSummary, listTestRuns, mediaUrl, setTestReviewBin, thumbUrl } from "./api";
import { REVIEW_BINS, binsForPreset } from "./reviewBins";

function inBin(item, folder) {
  const bin = item?.meta?.review_bin;
  if (folder.unfiled) return !bin;
  return bin === folder.id;
}

export default function TestReview({ onOpenLightbox }) {
  const [folderId, setFolderId] = useState(null);
  const [summary, setSummary] = useState({ review: {}, runs: {} });
  const [runs, setRuns] = useState([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  const folder = REVIEW_BINS.find((b) => b.id === folderId) || null;

  const refreshSummary = useCallback(async () => {
    try {
      const data = await getTestSummary();
      setSummary({
        review: data.review || {},
        runs: data.runs || {},
      });
    } catch (err) {
      setStatus(String(err.message || err));
      setError(true);
    }
  }, []);

  const refreshFolder = useCallback(async (id) => {
    const f = REVIEW_BINS.find((b) => b.id === id);
    if (!f) {
      setRuns([]);
      return;
    }
    try {
      const data = await listTestRuns({ presetId: f.presetId, limit: 50 });
      const items = Array.isArray(data.items) ? data.items : [];
      setRuns(items.filter((item) => inBin(item, f)));
    } catch (err) {
      setStatus(String(err.message || err));
      setError(true);
    }
  }, []);

  useEffect(() => {
    refreshSummary();
  }, [refreshSummary]);

  useEffect(() => {
    refreshFolder(folderId);
  }, [folderId, refreshFolder]);

  async function fileInto(itemId, bin) {
    if (!itemId) return;
    setBusy(true);
    try {
      await setTestReviewBin(itemId, bin);
      setStatus(bin ? "Moved." : "Sent back to unfiled.");
      setError(false);
      await Promise.all([refreshSummary(), refreshFolder(folderId)]);
    } catch (err) {
      setStatus(String(err.message || err));
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  function countFor(folderDef) {
    if (folderDef.unfiled) {
      const total = Number(summary.runs[folderDef.presetId] || 0);
      const filed = REVIEW_BINS.filter(
        (b) => b.presetId === folderDef.presetId && !b.unfiled
      ).reduce((n, b) => n + Number(summary.review[b.id] || 0), 0);
      return Math.max(0, total - filed);
    }
    return Number(summary.review[folderDef.id] || 0);
  }

  if (!folderId) {
    return (
      <section className="section refs-section">
        <div className="section-head">
          <h2 className="section-title">Review</h2>
          <span className="setting-hint">training folders for the active buttons</span>
        </div>
        <p className="refs-lead">
          Sort each test run into a folder. Keep = close enough to the refs.
          The other folders are the failure mode so we can change code or
          models next.
        </p>
        <div className="ref-folders">
          {REVIEW_BINS.map((b) => (
            <button
              key={b.id}
              type="button"
              className="ref-folder"
              onClick={() => setFolderId(b.id)}
            >
              <span className="ref-folder-label">{b.label}</span>
              <span className="ref-folder-hint">{b.hint}</span>
              <span className="ref-folder-meta">{countFor(b)} image{countFor(b) === 1 ? "" : "s"}</span>
            </button>
          ))}
        </div>
        {status ? (
          <p className={`status${error ? " error" : ""}`} role="status">
            {status}
          </p>
        ) : null}
      </section>
    );
  }

  const moveBins = binsForPreset(folder.presetId);

  return (
    <section className="section refs-section">
      <div className="section-head">
        <button type="button" className="ghost" onClick={() => setFolderId(null)}>
          All folders
        </button>
        <h2 className="section-title">{folder.label}</h2>
        <span className="setting-hint">{folder.hint}</span>
      </div>

      {runs.length === 0 ? (
        <p className="muted">Nothing in this folder yet.</p>
      ) : (
        <div className="gallery ref-gallery">
          {runs.map((item) => (
            <div key={item.id} className="ref-card">
              <button
                type="button"
                className="gallery-item"
                onClick={() => onOpenLightbox?.(item)}
              >
                <img src={thumbUrl(item) || mediaUrl(item)} alt="" loading="lazy" />
              </button>
              <div className="ref-card-actions ref-card-actions-wrap">
                {moveBins.map((b) =>
                  b.id === folder.id ? null : (
                    <button
                      key={b.id}
                      type="button"
                      className="ghost"
                      disabled={busy}
                      onClick={() => fileInto(item.id, b.id)}
                    >
                      {b.label.replace(/^.*·\s*/, "")}
                    </button>
                  )
                )}
                {!folder.unfiled && (
                  <button
                    type="button"
                    className="ghost ref-del"
                    disabled={busy}
                    onClick={() => fileInto(item.id, null)}
                  >
                    Unfile
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {status ? (
        <p className={`status${error ? " error" : ""}`} role="status">
          {status}
        </p>
      ) : null}
    </section>
  );
}
