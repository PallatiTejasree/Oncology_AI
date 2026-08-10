import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaBoxArchive, FaClockRotateLeft, FaFile, FaImage, FaTrash } from "react-icons/fa6";
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
      const result = session.latest_summary?.result;
      if (!result) throw new Error("This analysis does not have a completed result yet.");
      navigate("/results", { state: {
        result: { session_id: sessionId, ...result },
        prompt: session.original_query || "Analyze this uploaded file",
        attachments: [
          ...(session.reports || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "report" })),
          ...(session.images || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "image" })),
        ],
      } });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message || "Unable to open result.");
    }
  };

  const removeSession = async (sessionId) => {
    if (!window.confirm("Delete this analysis and its uploaded files?")) return;
    try {
      setDeleting(sessionId);
      await deleteUploadSession(sessionId);
      setSessions((current) => current.filter((item) => item.session_id !== sessionId));
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
    } catch (requestError) { setError(requestError.response?.data?.detail || "Unable to archive analysis."); }
  };

  return (
    <main className="history-page">
      <section className="history-shell">
        <header className="history-header">
          <button className="history-back" onClick={() => navigate("/dashboard")} aria-label="Back to dashboard"><FaArrowLeft /></button>
          <div><p>ONCOLOGY AI · PRIVATE WORKSPACE</p><h1>Analysis History</h1></div>
        </header>
        {error && <div className="history-error" role="alert">{error}</div>}
        {loading ? <div className="history-empty">Loading your analyses…</div> : sessions.length === 0 ? (
          <div className="history-empty"><FaClockRotateLeft /><h2>No analyses yet</h2><p>Your text queries and uploaded-file analyses will appear here.</p><button onClick={() => navigate("/dashboard")}>Start an analysis</button></div>
        ) : (
          <div className="history-list">
            {sessions.map((session) => (
              <article className="history-item" key={session.session_id}>
                <button className="history-open" onClick={() => openResult(session.session_id)} disabled={session.status !== "Completed"}>
                  <span className="history-type">{session.input_type === "image" ? <FaImage /> : <FaFile />}</span>
                  <span className="history-copy"><strong>{session.display_title || session.session_name}</strong><small>{formatDate(session.created_at)} · {session.input_type || "upload"}</small></span>
                  <span className={`history-status status-${session.status?.toLowerCase()}`}>{session.status}</span>
                </button>
                <button className="history-restore" onClick={() => archiveSession(session.session_id)} aria-label="Archive analysis"><FaBoxArchive /></button>
                <button className="history-delete" onClick={() => removeSession(session.session_id)} disabled={deleting === session.session_id} aria-label="Delete analysis"><FaTrash /></button>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
