import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaBoxArchive, FaRotateLeft, FaTrash } from "react-icons/fa6";
import { deleteUploadSession, getArchivedSessions, restoreUploadSession } from "../../services/uploadService";
import "../History/History.css";

const formatDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Unknown date";

export default function Archive() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getArchivedSessions().then(setSessions).catch((requestError) => setError(requestError.response?.data?.detail || "Unable to load archive.")).finally(() => setLoading(false));
  }, []);

  const restore = async (id) => {
    try { await restoreUploadSession(id); setSessions((items) => items.filter((item) => item.session_id !== id)); }
    catch (requestError) { setError(requestError.response?.data?.detail || "Unable to restore analysis."); }
  };
  const remove = async (id) => {
    if (!window.confirm("Permanently delete this archived analysis and its uploaded files? This cannot be undone.")) return;
    try { await deleteUploadSession(id); setSessions((items) => items.filter((item) => item.session_id !== id)); }
    catch (requestError) { setError(requestError.response?.data?.detail || "Unable to delete analysis."); }
  };

  return <main className="history-page"><section className="history-shell">
    <header className="history-header"><button className="history-back" onClick={() => navigate("/settings")}><FaArrowLeft /></button><div><p>ONCOLOGY AI · PRIVATE WORKSPACE</p><h1>Archive</h1></div></header>
    {error && <div className="history-error">{error}</div>}
    {loading ? <div className="history-empty">Loading archive…</div> : sessions.length === 0 ? <div className="history-empty"><FaBoxArchive /><h2>Archive is empty</h2><p>Analyses archived from History will appear here.</p><button onClick={() => navigate("/history")}>Open History</button></div> : <div className="history-list">{sessions.map((session) => <article className="history-item" key={session.session_id}><div className="history-open archive-copy"><span className="history-type"><FaBoxArchive /></span><span className="history-copy"><strong>{session.display_title || session.session_name}</strong><small>Archived {formatDate(session.archived_at)}</small></span></div><button className="history-restore" onClick={() => restore(session.session_id)} aria-label="Restore analysis"><FaRotateLeft /></button><button className="history-delete" onClick={() => remove(session.session_id)} aria-label="Permanently delete"><FaTrash /></button></article>)}</div>}
  </section></main>;
}
