import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaBoxArchive, FaCheck, FaClockRotateLeft, FaFile, FaImage, FaTrash } from "react-icons/fa6";
import { archiveUploadSession, deleteUploadSession, getUploadHistory, getUploadSession } from "../../services/uploadService";
import "./History.css";

const formatDate = (value) => value
  ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
  : "Unknown date";

export default function History() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [selected, setSelected] = useState([]);

  const loadHistory = useCallback(async () => {
    try {
      setError("");
      const email = localStorage.getItem("email");
      if (!email) throw new Error("Please sign in again.");
      setSessions(await getUploadHistory(email));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message || "Unable to load history.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const openResult = async (sessionId) => {
    try {
      const session = await getUploadSession(sessionId);
      const result = session.analyses?.[0]?.result || (session.input_type === "text" && session.messages?.length
        ? { response_type: "conversation", query_type: "conversation", summary: session.messages[0].answer }
        : session.latest_summary?.result);
      if (!result) throw new Error("This analysis does not have a completed result yet.");
      navigate("/results", { state: {
        result: { session_id: sessionId, ...result },
        prompt: session.analyses?.[0]?.question || session.original_query || "Analyze this uploaded file",
        attachments: session.analyses?.[0]?.attachments || [
          ...(session.reports || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "report" })),
          ...(session.images || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "image" })),
        ],
        savedMessages: session.messages || [],
        savedAnalyses: session.analyses || [],
      } });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message || "Unable to open result.");
    }
  };

  const removeSession = async (sessionId) => {
    try {
      setDeleting(sessionId);
      await deleteUploadSession(sessionId);
      setSessions((current) => current.filter((item) => item.session_id !== sessionId));
      setConfirmation(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to delete analysis.");
    } finally {
      setDeleting(null);
    }
  };

  const archiveSession = async (sessionId) => {
    try {
      await archiveUploadSession(sessionId);
      setSessions((current) => current.filter((item) => item.session_id !== sessionId));
      setConfirmation(null);
    } catch (requestError) { setError(requestError.response?.data?.detail || "Unable to archive analysis."); }
  };

  const toggleSelected = (sessionId) => {
    setSelected((current) => current.includes(sessionId)
      ? current.filter((id) => id !== sessionId)
      : [...current, sessionId]);
  };

  const requestBulkAction = (type, scope) => {
    const targets = scope === "all" ? sessions.map((item) => item.session_id) : selected;
    if (!targets.length) return;
    setConfirmation({ type, targets, scope });
  };

  const performBulkAction = async () => {
    const { type, targets } = confirmation;
    const completed = [];
    setDeleting("bulk");
    setError("");
    try {
      for (const sessionId of targets) {
        if (type === "delete") await deleteUploadSession(sessionId);
        else await archiveUploadSession(sessionId);
        completed.push(sessionId);
      }
      setSessions((current) => current.filter((item) => !completed.includes(item.session_id)));
      setSelected((current) => current.filter((id) => !completed.includes(id)));
      setConfirmation(null);
    } catch (requestError) {
      setSessions((current) => current.filter((item) => !completed.includes(item.session_id)));
      setSelected((current) => current.filter((id) => !completed.includes(id)));
      setError(requestError.response?.data?.detail || `Unable to ${type} all selected analyses.`);
      setConfirmation(null);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <main className="history-page">
      <section className="history-shell">
        <header className="history-header">
          <button className="history-back" onClick={() => navigate("/dashboard")} aria-label="Back to dashboard"><FaArrowLeft /></button>
          <div><p>ONCOLOGY AI · PRIVATE WORKSPACE</p><h1>Analysis History</h1></div>
        </header>
        {error && <div className="history-error" role="alert">{error}</div>}
        {!loading && sessions.length > 0 && <div className="history-bulk-toolbar">
          <button className="history-select-all" onClick={() => setSelected(selected.length === sessions.length ? [] : sessions.map((item) => item.session_id))}><FaCheck /> {selected.length === sessions.length ? "Clear selection" : "Select all"}</button>
          <span>{selected.length} selected</span>
          <div>
            <button disabled={!selected.length || deleting === "bulk"} onClick={() => requestBulkAction("archive", "selected")}><FaBoxArchive /> Archive selected</button>
            <button className="bulk-delete" disabled={!selected.length || deleting === "bulk"} onClick={() => requestBulkAction("delete", "selected")}><FaTrash /> Delete selected</button>
            <button onClick={() => requestBulkAction("archive", "all")} disabled={deleting === "bulk"}><FaBoxArchive /> Archive all</button>
            <button className="bulk-delete" onClick={() => requestBulkAction("delete", "all")} disabled={deleting === "bulk"}><FaTrash /> Delete all</button>
          </div>
        </div>}
        {loading ? <div className="history-empty">Loading your analyses…</div> : sessions.length === 0 ? (
          <div className="history-empty"><FaClockRotateLeft /><h2>No analyses yet</h2><p>Your text queries and uploaded-file analyses will appear here.</p><button onClick={() => navigate("/dashboard")}>Start an analysis</button></div>
        ) : (
          <div className="history-list">
            {sessions.map((session) => (
              <article className={`history-item ${selected.includes(session.session_id) ? "selected" : ""}`} key={session.session_id}>
                <label className="history-select" aria-label={`Select ${session.display_title || session.session_name}`}><input type="checkbox" checked={selected.includes(session.session_id)} onChange={() => toggleSelected(session.session_id)} /><span><FaCheck /></span></label>
                <button className="history-open" onClick={() => openResult(session.session_id)} disabled={session.status !== "Completed"}>
                  <span className="history-type">{session.input_type === "image" ? <FaImage /> : <FaFile />}</span>
                  <span className="history-copy"><strong>{session.display_title || session.session_name}</strong><small>{formatDate(session.created_at)} · {session.input_type || "upload"}</small></span>
                  <span className={`history-status status-${session.status?.toLowerCase()}`}>{session.status}</span>
                </button>
                <button className="history-restore" onClick={() => setConfirmation({ type:"archive", session })} aria-label="Archive analysis"><FaBoxArchive /></button>
                <button className="history-delete" onClick={() => setConfirmation({ type:"delete", session })} disabled={deleting === session.session_id} aria-label="Delete analysis"><FaTrash /></button>
              </article>
            ))}
          </div>
        )}
      </section>
      {confirmation && <div className="history-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setConfirmation(null); }}>
        <section className="history-dialog" role="dialog" aria-modal="true">
          <span className={confirmation.type === "delete" ? "danger" : "archive"}>{confirmation.type === "delete" ? <FaTrash /> : <FaBoxArchive />}</span>
          <h2>{confirmation.type === "delete" ? `Delete ${confirmation.targets ? confirmation.targets.length : 1} chat${confirmation.targets?.length === 1 ? "" : "s"}?` : `Archive ${confirmation.targets ? confirmation.targets.length : 1} analysis${confirmation.targets?.length === 1 ? "" : "es"}?`}</h2>
          <p>{confirmation.type === "delete"
            ? "This permanently removes the complete chat, answers, uploaded files, database records, and private vectors. This cannot be undone."
            : "This moves the analysis out of History and into Archive. You can restore it later."}</p>
          <strong>{confirmation.session ? (confirmation.session.display_title || confirmation.session.session_name) : confirmation.scope === "all" ? "All analyses in History" : `${confirmation.targets.length} selected analyses`}</strong>
          <div><button onClick={() => setConfirmation(null)}>Cancel</button><button className={confirmation.type === "delete" ? "confirm-delete" : "confirm-archive"} onClick={() => confirmation.targets ? performBulkAction() : confirmation.type === "delete" ? removeSession(confirmation.session.session_id) : archiveSession(confirmation.session.session_id)}>{confirmation.type === "delete" ? "Okay, delete" : "Okay, archive"}</button></div>
        </section>
      </div>}
    </main>
  );
}
