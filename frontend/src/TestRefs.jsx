import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteTestRef,
  getTestSummary,
  listTestRefs,
  listTestRuns,
  mediaUrl,
  testRefThumbUrl,
  thumbUrl,
  uploadTestRef,
} from "./api";
import { ACTION_PRESETS } from "./presets";

export default function TestRefs({ onOpenLightbox }) {
  const [folderId, setFolderId] = useState(null);
  const [summary, setSummary] = useState({ refs: {}, runs: {} });
  const [refs, setRefs] = useState([]);
  const [runs, setRuns] = useState([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const folder = ACTION_PRESETS.find((p) => p.id === folderId) || null;

  const refreshSummary = useCallback(async () => {
    try {
      const data = await getTestSummary();
      setSummary({
        refs: data.refs || {},
        runs: data.runs || {},
      });
    } catch (err) {
      setStatus(String(err.message || err));
      setError(true);
    }
  }, []);

  const refreshFolder = useCallback(async (id) => {
    if (!id) {
      setRefs([]);
      setRuns([]);
      return;
    }
    try {
      const [refData, runData] = await Promise.all([
        listTestRefs(id),
        listTestRuns({ presetId: id, limit: 50 }),
      ]);
      setRefs(Array.isArray(refData.items) ? refData.items : []);
      setRuns(Array.isArray(runData.items) ? runData.items : []);
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

  async function onUpload(files) {
    if (!folderId || !files?.length) return;
    setBusy(true);
    setError(false);
    try {
      let n = 0;
      for (const file of files) {
        if (!file.type.startsWith("image/")) continue;
        await uploadTestRef(folderId, file);
        n += 1;
      }
      setStatus(n ? `Saved ${n} reference image${n === 1 ? "" : "s"}.` : "No images selected.");
      await Promise.all([refreshSummary(), refreshFolder(folderId)]);
    } catch (err) {
      setStatus(String(err.message || err));
      setError(true);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function onDelete(id) {
    if (!id) return;
    if (!window.confirm("Remove this reference image?")) return;
    setBusy(true);
    try {
      await deleteTestRef(id);
      setStatus("Reference removed.");
      setError(false);
      await Promise.all([refreshSummary(), refreshFolder(folderId)]);
    } catch (err) {
      setStatus(String(err.message || err));
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  if (!folderId) {
    return (
      <section className="section refs-section">
        <div className="section-head">
          <h2 className="section-title">Reference generations</h2>
          <span className="setting-hint">one folder per generate button</span>
        </div>
        <p className="refs-lead">
          Drop target looks here. Put example outputs in the folder that matches the
          generate button.
        </p>
        <div className="ref-folders">
          {ACTION_PRESETS.map((p) => {
            const refN = Number(summary.refs[p.id] || 0);
            const runN = Number(summary.runs[p.id] || 0);
            return (
              <button
                key={p.id}
                type="button"
                className="ref-folder"
                onClick={() => setFolderId(p.id)}
              >
                <span className="ref-folder-top">
                  <span className="ref-folder-label">{p.label}</span>
                  <span
                    className={`ref-folder-mode${p.mode === "vid" ? " vid" : " img"}`}
                  >
                    {p.mode === "vid" ? "Video" : "Image"}
                  </span>
                </span>
                <span className="ref-folder-hint">{p.hint}</span>
                <span className="ref-folder-meta">
                  {refN} ref{refN === 1 ? "" : "s"} · {runN} test run{runN === 1 ? "" : "s"}
                </span>
              </button>
            );
          })}
        </div>
        {status ? (
          <p className={`status${error ? " error" : ""}`} role="status">
            {status}
          </p>
        ) : null}
      </section>
    );
  }

  return (
    <section className="section refs-section">
      <div className="section-head">
        <button type="button" className="ghost" onClick={() => setFolderId(null)}>
          All folders
        </button>
        <h2 className="section-title">
          {folder?.label || folderId}
          <span className={`ref-folder-mode${folder?.mode === "vid" ? " vid" : " img"}`}>
            {folder?.mode === "vid" ? "Video" : "Image"}
          </span>
        </h2>
        <span className="setting-hint">{folder?.hint}</span>
      </div>

      <label className="drop ref-drop">
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          disabled={busy}
          onChange={(e) => onUpload(e.target.files)}
        />
        <div className="drop-inner">
          <span className="drop-title">
            {busy ? "Uploading…" : "Tap to add reference images"}
          </span>
          <span className="drop-sub">Stored in this PIN’s cloud library — not on this PC</span>
        </div>
      </label>

      <h3 className="refs-sub">References</h3>
      {refs.length === 0 ? (
        <p className="muted">No references in this folder yet.</p>
      ) : (
        <div className="gallery ref-gallery">
          {refs.map((item) => (
            <div key={item.id} className="ref-card">
              <button
                type="button"
                className="gallery-item"
                onClick={() => onOpenLightbox?.({ ...item, _testRef: true, kind: "img" })}
              >
                <img src={testRefThumbUrl(item)} alt="" loading="lazy" />
              </button>
              <button
                type="button"
                className="ghost ref-del"
                disabled={busy}
                onClick={() => onDelete(item.id)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      <h3 className="refs-sub">Your test runs for this button</h3>
      {runs.length === 0 ? (
        <p className="muted">No test generations tagged to this button yet.</p>
      ) : (
        <div className="gallery ref-gallery">
          {runs.map((item) => (
            <button
              key={item.id}
              type="button"
              className="gallery-item"
              onClick={() => onOpenLightbox?.(item)}
            >
              <img
                src={thumbUrl(item) || mediaUrl(item)}
                alt=""
                loading="lazy"
              />
            </button>
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
