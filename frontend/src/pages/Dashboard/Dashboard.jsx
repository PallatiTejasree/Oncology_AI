import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import {
  FaArrowRightFromBracket,
  FaBoxArchive,
  FaClockRotateLeft,
  FaGear,
  FaImage,
  FaMessage,
  FaPaperPlane,
  FaPen,
  FaPlus,
  FaRegImage,
  FaRegUser,
  FaShieldHalved,
  FaTrash,
  FaXmark,
} from "react-icons/fa6";


import { archiveUploadSession, deleteUploadSession, getUploadHistory, getUploadSession, renameUploadSession, uploadFiles } from "../../services/uploadService";

import "./Dashboard.css";
import oncologyLogo from "../../assets/oncology-ai-logo.png";

const morningGreetings = [
  "Good Morning! Ready to review today's clinical cases?",
  "Good Morning! Let's explore today's medical insights.",
  "A healthy morning starts with informed decisions.",
  "Good Morning! Your AI clinical assistant is ready.",
];

const afternoonGreetings = [
  "Good Afternoon! Let's continue improving patient care.",
  "Good Afternoon! Ready for another medical analysis?",
  "Hope your day is going well. Let's review some cases.",
  "Good Afternoon! AI-powered insights are ready for you.",
];

const eveningGreetings = [
  "Good Evening! Let's wrap up today's clinical work.",
  "Good Evening! Ready to analyze another report?",
  "Hope you had a productive day. Let's continue.",
  "Good Evening! Your Oncology AI is standing by.",
];

const nightGreetings = [
  "Night Owl? Let's solve one more medical case.",
  "Working late? Oncology AI is always available.",
  "Late-night research? Let's discover new insights.",
  "Even at night, better decisions begin with better data.",
];

const suggestions = [
  "Summarize this pathology report",
  "Explain findings from this MRI scan",
  "Compare this case with similar oncology reports",
];

const MAX_UPLOAD_FILES = 3;

export default function Dashboard() {
  const navigate = useNavigate();

  const fileInputRef = useRef(null);
  const recentClickTimerRef = useRef(null);

  const [message, setMessage] = useState("");

  const [uploading, setUploading] = useState(false);
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [uploadSessionId, setUploadSessionId] = useState(null);
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameSaving, setRenameSaving] = useState(false);
  const [renameError, setRenameError] = useState("");
  const [recentMenu, setRecentMenu] = useState(null);
  const [recentConfirmation, setRecentConfirmation] = useState(null);
  const [recentActionBusy, setRecentActionBusy] = useState(false);

  useEffect(() => {
    const email = localStorage.getItem("email");
    if (!email) return;
    getUploadHistory(email)
      .then((items) => setRecentAnalyses(items.slice(0, 20)))
      .catch(() => setRecentAnalyses([]));
  }, []);

  const openRecentAnalysis = async (sessionId) => {
    try {
      const session = await getUploadSession(sessionId);
      const saved = session.analyses?.[0]?.result || (session.input_type === "text" && session.messages?.length
        ? { response_type: "conversation", query_type: "conversation", summary: session.messages[0].answer }
        : session.latest_summary?.result);
      if (!saved) throw new Error("This analysis is not complete yet.");
      navigate("/results", {
        state: {
          result: { session_id: sessionId, ...saved },
          prompt: session.analyses?.[0]?.question || session.original_query || "Analyze this uploaded file",
          attachments: session.analyses?.[0]?.attachments || [
            ...(session.reports || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "report" })),
            ...(session.images || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "image" })),
          ],
          savedMessages: session.messages || [],
          savedAnalyses: session.analyses || [],
        },
      });
    } catch (error) {
      window.alert(error.response?.data?.detail || error.message || "Unable to open this analysis.");
    }
  };

  const saveRecentName = async (event) => {
    event.preventDefault();
    const cleanName = renameValue.trim();
    if (!cleanName || !renameTarget || renameSaving) return;
    setRenameSaving(true);
    setRenameError("");
    try {
      const response = await renameUploadSession(renameTarget.session_id, cleanName);
      setRecentAnalyses((items) => items.map((item) => item.session_id === renameTarget.session_id
        ? { ...item, session_name: response.name, display_title: response.name }
        : item));
      setRenameTarget(null);
      setRenameValue("");
    } catch (requestError) {
      setRenameError(requestError.response?.data?.detail || "Unable to rename this analysis.");
    } finally {
      setRenameSaving(false);
    }
  };

  const clickRecent = (item) => {
    window.clearTimeout(recentClickTimerRef.current);
    if (item.status === "Completed") {
      recentClickTimerRef.current = window.setTimeout(() => openRecentAnalysis(item.session_id), 240);
    }
  };

  const openRecentMenu = (event, item) => {
    event.preventDefault();
    window.clearTimeout(recentClickTimerRef.current);
    setRecentMenu({
      item,
      x: Math.min(event.clientX, window.innerWidth - 175),
      y: Math.min(event.clientY, window.innerHeight - 145),
    });
  };

  const runRecentAction = async () => {
    if (!recentConfirmation || recentActionBusy) return;
    setRecentActionBusy(true);
    try {
      if (recentConfirmation.type === "delete") await deleteUploadSession(recentConfirmation.item.session_id);
      else await archiveUploadSession(recentConfirmation.item.session_id);
      setRecentAnalyses((items) => items.filter((item) => item.session_id !== recentConfirmation.item.session_id));
      setRecentConfirmation(null);
      setRecentMenu(null);
    } catch (requestError) {
      window.alert(requestError.response?.data?.detail || `Unable to ${recentConfirmation.type} this analysis.`);
    } finally {
      setRecentActionBusy(false);
    }
  };

  const [{ greeting, subtitle }] = useState(() => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return { greeting: morningGreetings[Math.floor(Math.random() * morningGreetings.length)], subtitle: "Let's make today healthier together." };
    if (hour >= 12 && hour < 18) return { greeting: afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)], subtitle: "Your AI assistant is ready to help." };
    if (hour >= 18 && hour < 24) return { greeting: eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)], subtitle: "Review reports and images with confidence." };
    return { greeting: nightGreetings[Math.floor(Math.random() * nightGreetings.length)], subtitle: "Even the best discoveries sometimes happen after midnight." };
  });

  const submitMessage = (e) => {
    e.preventDefault();

    if (!message.trim() && !uploadSessionId) return;

    const text = message.trim();
    setMessage("");
    navigate("/results", {
      state: {
        pendingAnalysis: uploadSessionId
          ? { sessionId: uploadSessionId, text, attachments: attachedFiles }
          : { text, attachments: [] },
      },
    });
  };

  const handleFileUpload = async (event) => {
    const selectedFiles = Array.from(event.target.files);
    const files = selectedFiles.slice(0, MAX_UPLOAD_FILES);

    if (!files.length) return;

    if (selectedFiles.length > MAX_UPLOAD_FILES) {
      window.alert(`Only ${MAX_UPLOAD_FILES} files can be uploaded at once. The first ${MAX_UPLOAD_FILES} files will be added.`);
    }

    setUploading(true);

    try {
      const email = localStorage.getItem("email");

      const response = await uploadFiles(
        email,
        files
      );

      if (response.ignored_files?.length) {
        window.alert(response.message);
      }

      setUploadSessionId(response.session_id);
      setAttachedFiles(files.map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type,
        kind: file.type.startsWith("image/") ? "image" : "report",
        previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
      })));
    } catch (error) {
      console.error(error);
      alert("Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const removeAttachment = async () => {
    const sessionId = uploadSessionId;
    setUploadSessionId(null);
    setAttachedFiles((current) => {
      current.forEach((file) => file.previewUrl && URL.revokeObjectURL(file.previewUrl));
      return [];
    });
    if (sessionId) {
      try { await deleteUploadSession(sessionId); } catch (error) { console.error(error); }
    }
  };

  const chooseSuggestion = (text) => {
    setMessage(text);
  };

  return (
    <div className="clinical-dashboard">

      <aside className="clinical-sidebar">

        <div className="clinical-brand">

          <div className="clinical-brand-icon"><img src={oncologyLogo} alt="Oncology AI logo" /></div>

          <div>
            <h1>Oncology AI</h1>
            <p>Enterprise Clinical Intelligence</p>
          </div>

        </div>

        <button
          className="clinical-new-analysis"
          type="button"
          onClick={() => {
            setMessage("");
            removeAttachment();
          }}
        >
          <FaPlus />
          <span>New Analysis</span>
        </button>

        <nav className="clinical-nav">

          <button className="active">
            <FaMessage />
            Medical AI Assistant
          </button>

          <button
            onClick={() =>
              fileInputRef.current?.click()
            }
          >
            <FaRegImage />
            Upload
          </button>

          <button type="button" onClick={() => navigate("/history")}>
            <FaClockRotateLeft />
            History
          </button>

          <button
            type="button"
            className="clinical-profile-link"
            onClick={() => navigate("/profile")}
          >
            <FaRegUser />
            Profile
          </button>

         <button onClick={() => navigate("/settings")}>

  <FaGear />

  Settings

</button>

        </nav>

        <section className="clinical-recents">

          <h2>Recent Analyses</h2>

          {recentAnalyses.length === 0 ? (
            <p>Your recent AI analyses will appear here.</p>
          ) : recentAnalyses.map((item) => (
            <div className="clinical-recent-row" key={item.session_id}>
              <button className={item.status !== "Completed" ? "not-ready" : ""} type="button" onClick={() => clickRecent(item)} onDoubleClick={(event) => openRecentMenu(event, item)} aria-disabled={item.status !== "Completed"} title="Click to open · Double-click for actions">{item.display_title || item.session_name}</button>
            </div>
          ))}

        </section>

        <div className="clinical-sidebar-bottom">

          <p className="clinical-support">

            <FaShieldHalved />

            Clinical Decision Support

          </p>

          <button
            className="clinical-logout"
            onClick={() => {
              localStorage.clear();
              navigate("/");
            }}
          >

            <FaArrowRightFromBracket />

            Logout

          </button>

        </div>

      </aside>

      <main className="clinical-main">

        <header className="clinical-topbar">

          <div className="clinical-user">

            <span>T</span>

            <strong>Tejasree</strong>

          </div>

        </header>

        <motion.section
          className="clinical-hero"
          initial={{
            opacity: 0,
            y: 20,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            duration: 0.6,
          }}
        >

          <div className="clinical-copilot-mark">

            <img src={oncologyLogo} alt="Oncology AI logo" />

            <FaImage />

          </div>

          <h2>{greeting}</h2>

          <p className="clinical-intro">

            {subtitle}

          </p>

          <form
            className="clinical-composer"
            onSubmit={submitMessage}
          >

            {attachedFiles.length > 0 && (
              <div className="clinical-attachments">
                {attachedFiles.map((file) => (
                  <div className="clinical-attachment" key={file.name}>
                    {file.previewUrl ? <img src={file.previewUrl} alt={`Preview of ${file.name}`} /> : <FaRegImage />}
                    <span><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB · Ready</small></span>
                  </div>
                ))}
                <button type="button" onClick={removeAttachment} aria-label="Remove uploaded files"><FaXmark /></button>
              </div>
            )}

            <textarea
              aria-label="Message to medical AI assistant"
              placeholder="Ask about a pathology report, MRI, CT scan, biopsy, diagnosis, treatment, or upload medical files..."
              value={message}
              onChange={(e) =>
                setMessage(e.target.value)
              }
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey
                ) {
                  e.preventDefault();
                  submitMessage(e);
                }
              }}
            />

            <div className="clinical-composer-actions">

              <button
                className="clinical-upload"
                type="button"
                disabled={uploading || Boolean(uploadSessionId)}
                onClick={() =>
                  fileInputRef.current?.click()
                }
              >

                <FaRegImage />

                {uploading
                  ? "Uploading..."
                  : "Upload"}

              </button>

              <button
                className="clinical-send"
                type="submit"
                disabled={!message.trim() && !uploadSessionId}
                aria-label="Send message"
              >

                <FaPaperPlane />

              </button>

            </div>

            <input
              ref={fileInputRef}
              type="file"
              hidden
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileUpload}
            />

          </form>

          <div className="clinical-suggestions">
                        {suggestions.map((suggestion) => (

              <button
                key={suggestion}
                type="button"
                onClick={() => chooseSuggestion(suggestion)}
              >

                {suggestion}

              </button>

            ))}

          </div>

        </motion.section>

        <footer className="clinical-footer">
          <p className="clinical-disclaimer">
            <strong>Disclaimer:</strong> Oncology AI is designed to assist
            healthcare professionals by summarizing reports, analyzing medical
            images, and retrieving relevant clinical information. It is not a
            substitute for professional medical judgment, diagnosis, or
            treatment.
          </p>
        </footer>

      </main>

      {renameTarget && <div className="dashboard-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setRenameTarget(null); }}>
        <form className="dashboard-rename-dialog" onSubmit={saveRecentName}>
          <span><FaPen /></span>
          <h2>Rename analysis</h2>
          <p>Choose a clear name that will appear in Recents, History, and Archive.</p>
          <label>Analysis name<input autoFocus maxLength="80" value={renameValue} onChange={(event) => setRenameValue(event.target.value)} /></label>
          {renameError && <small>{renameError}</small>}
          <div><button type="button" onClick={() => setRenameTarget(null)}>Cancel</button><button type="submit" disabled={!renameValue.trim() || renameSaving}>{renameSaving ? "Saving…" : "Save name"}</button></div>
        </form>
      </div>}
      {recentMenu && <div className="dashboard-context-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) setRecentMenu(null); }}>
        <section className="dashboard-recent-context" role="menu" style={{ left:recentMenu.x, top:recentMenu.y }}>
          <button type="button" role="menuitem" onClick={() => { setRenameTarget(recentMenu.item); setRenameValue(recentMenu.item.display_title || recentMenu.item.session_name || ""); setRenameError(""); setRecentMenu(null); }}><FaPen /> Rename</button>
          <button type="button" role="menuitem" onClick={() => { setRecentConfirmation({ type:"archive", item:recentMenu.item }); setRecentMenu(null); }}><FaBoxArchive /> Archive</button>
          <button className="danger" type="button" role="menuitem" onClick={() => { setRecentConfirmation({ type:"delete", item:recentMenu.item }); setRecentMenu(null); }}><FaTrash /> Delete</button>
        </section>
      </div>}
      {recentConfirmation && <div className="dashboard-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setRecentConfirmation(null); }}>
        <section className="dashboard-action-dialog" role="dialog" aria-modal="true">
          <span className={recentConfirmation.type}>{recentConfirmation.type === "delete" ? <FaTrash /> : <FaBoxArchive />}</span>
          <h2>{recentConfirmation.type === "delete" ? "Delete this chat?" : "Archive this chat?"}</h2>
          <p>{recentConfirmation.type === "delete" ? "This permanently removes the complete conversation, uploaded files, and private vectors. It cannot be undone." : "This moves the conversation to Archive. You can restore it later."}</p>
          <strong>{recentConfirmation.item.display_title || recentConfirmation.item.session_name}</strong>
          <div><button type="button" onClick={() => setRecentConfirmation(null)}>Cancel</button><button className={recentConfirmation.type === "delete" ? "danger" : "archive"} type="button" disabled={recentActionBusy} onClick={runRecentAction}>{recentActionBusy ? "Please wait…" : recentConfirmation.type === "delete" ? "Delete" : "Archive"}</button></div>
        </section>
      </div>}

    </div>
  );
}
