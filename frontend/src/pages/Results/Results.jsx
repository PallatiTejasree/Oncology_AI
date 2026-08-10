import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaHeartbeat } from "react-icons/fa";
import { FaClockRotateLeft, FaFilePdf, FaGear, FaImage, FaPaperclip, FaPaperPlane, FaPlus, FaRegUser, FaXmark } from "react-icons/fa6";
import { analyzeSession, analyzeText, clearConversationCache } from "../../services/analysisService";
import { deleteUploadSession, getUploadHistory, getUploadSession, uploadFiles } from "../../services/uploadService";
import "./Results.css";
import oncologyLogo from "../../assets/oncology-ai-logo.png";

function CareUrgency({ review }) {
  if (!review?.level) return null;
  return (
    <section className={`care-urgency urgency-${review.level}`} aria-label="Care urgency guidance">
      <div><small>Care urgency</small><strong>{review.label}</strong></div>
      <p>{review.message}</p>
      <span>Guidance only · not a diagnosis or risk probability</span>
    </section>
  );
}

function RiskReview({ review }) {
  if (!review?.rows?.length) return null;
  return (
    <section className="risk-review" aria-labelledby="risk-review-title">
      <div className="risk-review-heading">
        <div><h2 id="risk-review-title">Cancer risk review</h2><p>{review.explanation}</p></div>
        <span>{review.level}</span>
      </div>
      <div className="risk-table-wrap">
        <table>
          <thead><tr><th>Review area</th><th>Current status</th><th>What it means</th></tr></thead>
          <tbody>{review.rows.map((row) => <tr key={row.factor}><th scope="row">{row.factor}</th><td>{row.status}</td><td>{row.meaning}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function ResearchSummary({ summary }) {
  if (!summary) return null;
  return <div className="research-summary"><span>{summary.related_records || 0}</span><p><strong>Related evidence reviewed</strong><small>{summary.message}</small></p></div>;
}

function EvidenceList({ evidence = [], supportingImages = [], uploadedSources = [], citationValidation }) {
  const records = [...evidence, ...supportingImages];
  if (!records.length && !uploadedSources.length) return null;
  return (
    <section className="answer-evidence" aria-labelledby="answer-evidence-title">
      <div className="answer-evidence-heading">
        <div><h2 id="answer-evidence-title">Evidence</h2><p>Retrieved references used to prepare this answer</p></div>
        <span>{records.length} records</span>
      </div>
      {uploadedSources.length > 0 && <div className="uploaded-evidence">
        <h3>Uploaded material</h3>
        {uploadedSources.map((source, index) => <div key={`${source.file_name}-${index}`}><strong>[U{index + 1}] {source.file_name}</strong><span>{source.source_type?.replaceAll("_", " ")}</span></div>)}
      </div>}
      <ol>
        {records.map((item, index) => {
          const pmcid = item.pmcid || (String(item.id || "").match(/PMC\d+/i)?.[0]);
          const title = item.file_name || pmcid || item.document_id || item.image_id || `Indexed ${item.modality || "evidence"} record`;
          const excerpt = String(item.text || "").replace(/\s+/g, " ").trim();
          return (
            <li key={`${item.id || title}-${index}`}>
              <div className="evidence-title-row">
                <strong>[R{index + 1}] {title}</strong>
                <span>{item.modality === "image" ? "Image" : "Text"} · rank {item.rank || index + 1}</span>
              </div>
              {excerpt && <p>{excerpt.length > 260 ? `${excerpt.slice(0, 260)}…` : excerpt}</p>}
              <div className="evidence-meta">
                {item.cancer_type && item.cancer_type !== "unknown" && <span>{item.cancer_type.replaceAll("_", " ")}</span>}
                {item.source_dataset && <span>{item.source_dataset.replaceAll("_", " ")}</span>}
                {pmcid && <a href={`https://pmc.ncbi.nlm.nih.gov/articles/${pmcid}/`} target="_blank" rel="noreferrer">Open PMC source</a>}
              </div>
            </li>
          );
        })}
      </ol>
      {citationValidation?.status === "invalid" && <p className="citation-warning">Some generated citation identifiers could not be verified.</p>}
    </section>
  );
}

function ThinkingIndicator({ label = "Reviewing your question" }) {
  return (
    <div className="chat-thinking-box" role="status" aria-live="polite">
      <span className="chat-thinking-dots" aria-hidden="true"><i /><i /><i /></span>
      <div><strong>{label}</strong><small>Searching relevant oncology evidence and preparing a clear response…</small></div>
    </div>
  );
}

function MessageAttachments({ files = [] }) {
  if (!files.length) return null;
  return (
    <div className="message-attachments">
      {files.map((file, index) => (
        <div className="message-attachment" key={`${file.name}-${index}`}>
          {file.previewUrl
            ? <img src={file.previewUrl} alt={`Attached ${file.name}`} />
            : file.kind === "image" || file.type?.startsWith("image/")
              ? <span className="message-file-icon image"><FaImage /></span>
              : <span className="message-file-icon pdf"><FaFilePdf /></span>}
          <span className="message-file-copy"><strong>{file.name}</strong><small>{file.kind === "image" || file.type?.startsWith("image/") ? "Image" : "PDF document"}</small></span>
        </div>
      ))}
    </div>
  );
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  return value === undefined || value === null || value === "" ? [] : [value];
}

function asObjectArray(value) {
  return asArray(value).filter((item) => item && typeof item === "object" && !Array.isArray(item));
}

function displayText(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return JSON.stringify(value);
}

function CitationTags({ citations }) {
  const items = asArray(citations).map(displayText).filter(Boolean);
  if (!items.length) return null;
  return <span className="answer-citations">{items.map((citation, index) => <span key={`${citation}-${index}`}>{citation}</span>)}</span>;
}

function StructuredAnswer({ answer }) {
  if (!answer) return null;
  const findings = asObjectArray(answer.findings);
  const reasoning = asObjectArray(answer.reasoning);
  const supports = asArray(answer.supports).map(displayText).filter(Boolean);
  const limitations = asArray(answer.limitations).map(displayText).filter(Boolean);
  const medicalTerms = asObjectArray(answer.medical_terms);
  const supportClass = String(answer.evidence_support?.level || "limited").toLowerCase();
  return (
    <div className="clinical-answer">
      <section className="clinical-interpretation">
        <p>Clinical evidence summary</p>
        <h2>{displayText(answer.headline)}</h2>
        {answer.subheadline && <h3>{displayText(answer.subheadline)}</h3>}
        {answer.evidence_support && <div className={`evidence-support support-${supportClass}`}>
          <strong>{displayText(answer.evidence_support?.level || "Limited")} evidence support</strong>
          <span>{displayText(answer.evidence_support?.explanation || answer.evidence_support)}</span>
        </div>}
      </section>

      {answer.plain_language_summary && <section className="answer-section plain-summary">
        <h2>In simple terms</h2><p>{displayText(answer.plain_language_summary)}</p>
      </section>}

      {findings.length > 0 && <section className="answer-section">
        <h2>Findings at a glance</h2>
        <div className="findings-table-wrap"><table className="findings-table">
          <thead><tr><th>Finding</th><th>Result</th><th>What it means</th></tr></thead>
          <tbody>{findings.map((item, index) => <tr key={`${displayText(item.finding)}-${index}`}>
            <th scope="row">{displayText(item.finding)}<CitationTags citations={item.citations} /></th>
            <td>{displayText(item.result)}</td><td>{displayText(item.meaning)}</td>
          </tr>)}</tbody>
        </table></div>
      </section>}

      {reasoning.length > 0 && <section className="answer-section">
        <h2>Why the AI reached this interpretation</h2>
        <ol className="reasoning-list">{reasoning.map((item, index) => <li key={`${displayText(item.title)}-${index}`}>
          <span>{index + 1}</span><div><strong>{displayText(item.title)}</strong><p>{displayText(item.explanation)}</p><CitationTags citations={item.citations} /></div>
        </li>)}</ol>
      </section>}

      {(supports.length > 0 || limitations.length > 0) && <section className="answer-section">
        <h2>Evidence balance</h2><div className="evidence-balance">
          <div><h3>Supports the interpretation</h3>{supports.map((item, index) => <p key={index}>✓ {item}</p>)}</div>
          <div><h3>Important limitations</h3>{limitations.map((item, index) => <p key={index}>! {item}</p>)}</div>
        </div>
      </section>}

      {medicalTerms.length > 0 && <details className="medical-terms answer-section">
        <summary>Explain the medical terms</summary>
        <div>{medicalTerms.map((item, index) => <article key={`${displayText(item.term)}-${index}`}><strong>{displayText(item.term)}</strong><p>{displayText(item.definition)}</p></article>)}</div>
      </details>}

      {answer.safety_notice && <section className="answer-safety"><h2>Safety & interpretation</h2><p>{displayText(answer.safety_notice)}</p></section>}
    </div>
  );
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const initial = location.state?.result;
  const pendingAnalysis = location.state?.pendingAnalysis;
  const initialPrompt = pendingAnalysis?.text ?? location.state?.prompt;
  const initialAttachments = pendingAnalysis?.attachments ?? location.state?.attachments ?? [];
  const [displayedPrompt, setDisplayedPrompt] = useState(initialPrompt || "");
  const [displayedAttachments, setDisplayedAttachments] = useState(initialAttachments);
  const [result, setResult] = useState(initial);
  const [activeSessionId, setActiveSessionId] = useState(initial?.session_id || pendingAnalysis?.sessionId || null);
  const [initialLoading, setInitialLoading] = useState(Boolean(pendingAnalysis && !initial));
  const [turns, setTurns] = useState([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [attachment, setAttachment] = useState(null);
  const [uploading, setUploading] = useState(false);
  const followupFileRef = useRef(null);
  const initialRequestStarted = useRef(false);

  useEffect(() => {
    if (!pendingAnalysis || initial || initialRequestStarted.current) return;
    initialRequestStarted.current = true;
    const runInitialAnalysis = async () => {
      setInitialLoading(true);
      setError("");
      try {
        const next = pendingAnalysis.sessionId
          ? await analyzeSession(pendingAnalysis.sessionId, pendingAnalysis.text || "")
          : await analyzeText(pendingAnalysis.text || "");
        setResult(next);
        setActiveSessionId(next.session_id);
        navigate("/results", {
          replace: true,
          state: {
            result: next,
            prompt: pendingAnalysis.text || "Analyze this uploaded file",
            attachments: pendingAnalysis.attachments || [],
          },
        });
      } catch (requestError) {
        setError(requestError.response?.data?.detail || requestError.message || "Analysis failed.");
      } finally {
        setInitialLoading(false);
      }
    };
    runInitialAnalysis();
  }, [initial, navigate, pendingAnalysis]);

  useEffect(() => {
    const email = localStorage.getItem("email");
    if (!email) return;
    getUploadHistory(email).then((items) => setRecentAnalyses(items.slice(0, 5))).catch(() => setRecentAnalyses([]));
  }, [turns]);

  const attachAnotherFile = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setUploading(true); setError("");
    try {
      const response = await uploadFiles(localStorage.getItem("email"), files);
      const file = files[0];
      setActiveSessionId(response.session_id);
      setAttachment({ sessionId: response.session_id, name: file.name, previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null });
    } catch (requestError) { setError(requestError.response?.data?.detail || "Unable to upload file."); }
    finally { setUploading(false); event.target.value = ""; }
  };

  const removeFollowupAttachment = async () => {
    if (!attachment) return;
    const removed = attachment;
    setAttachment(null);
    setActiveSessionId(result.session_id);
    if (removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
    try { await deleteUploadSession(removed.sessionId); } catch (requestError) { console.error(requestError); }
  };

  const openRecent = async (sessionId) => {
    try {
      const session = await getUploadSession(sessionId);
      const saved = session.latest_summary?.result;
      if (!saved) throw new Error("This analysis is not complete.");
      setResult({ session_id: sessionId, ...saved });
      setActiveSessionId(sessionId);
      setDisplayedPrompt(session.original_query || "Analyze this uploaded file");
      setDisplayedAttachments([
        ...(session.reports || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "report" })),
        ...(session.images || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "image" })),
      ]);
      setTurns([]); setAttachment(null); window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (requestError) { setError(requestError.response?.data?.detail || requestError.message); }
  };

  const clearContext = async () => {
    if (!activeSessionId) return;
    try {
      await clearConversationCache(activeSessionId);
      setTurns([]);
      setError("");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to clear conversation context.");
    }
  };

  if (!result && !initialLoading && !pendingAnalysis) return <main className="chat-workspace"><div className="chat-no-result"><h1>No result available</h1><button onClick={() => navigate("/dashboard")}>Return to dashboard</button></div></main>;

  const sendFollowUp = async (event) => {
    event.preventDefault();
    const clean = question.trim();
    if ((!clean && !attachment) || !activeSessionId || sending) return;
    setQuestion(""); setError(""); setSending(true);
    try {
      const next = await analyzeSession(activeSessionId, clean);
      setTurns((current) => [...current, { question: clean || "Analyze this uploaded file", answer: next.summary, structuredAnswer: next.structured_answer, evidence: next.evidence, supportingImages: next.supporting_image_evidence, uploadedSources: next.uploaded_sources, citationValidation: next.citation_validation, careUrgency: next.care_urgency, previewUrl: attachment?.previewUrl, fileName: attachment?.name }]);
      setResult((current) => ({ ...current, session_id: activeSessionId }));
      setAttachment(null);
      window.setTimeout(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }), 0);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to answer the follow-up question.");
      setQuestion(clean);
    } finally { setSending(false); }
  };

  return (
    <div className="chat-workspace">
      <aside className="chat-sidebar">
        <div className="chat-brand"><span><img src={oncologyLogo} alt="Oncology AI logo" /></span><div><strong>Oncology AI</strong><small>Clinical Intelligence</small></div></div>
        <button className="chat-new" onClick={() => navigate("/dashboard")}><FaPlus /> New analysis</button>
        <nav><button onClick={() => navigate("/dashboard")}><FaHeartbeat /> Assistant</button><button onClick={() => navigate("/history")}><FaClockRotateLeft /> History</button><button onClick={() => navigate("/profile")}><FaRegUser /> Profile</button><button onClick={() => navigate("/settings")}><FaGear /> Settings</button></nav>
        <section className="chat-recents"><h2>Recents</h2>{recentAnalyses.length === 0 ? <p>No saved analyses yet.</p> : recentAnalyses.map((item) => <button key={item.session_id} onClick={() => openRecent(item.session_id)}>{item.display_title || item.session_name}</button>)}</section>
        <p className="chat-sidebar-note">Clinical decision support only</p>
      </aside>
      <main className="chat-main">
        <header className="chat-topbar"><div><small>ONCOLOGY AI · CLINICAL SUPPORT</small><strong>Analysis conversation</strong></div><span className="chat-topbar-actions"><button onClick={clearContext}>Clear context</button><button onClick={() => navigate("/history")}>History</button></span></header>
        <div className="chat-thread">
          {(displayedPrompt || displayedAttachments.length > 0) && (
            <article className="user-turn initial-user-turn"><div>
              <MessageAttachments files={displayedAttachments} />
              <p>{displayedPrompt || "Analyze this uploaded file"}</p>
            </div></article>
          )}
          {initialLoading && <article className="assistant-turn compact"><div className="assistant-avatar"><FaHeartbeat /></div><div className="assistant-content"><ThinkingIndicator label="Reviewing your clinical material" /></div></article>}
          {result && <article className="assistant-turn">
            <div className="assistant-avatar"><FaHeartbeat /></div>
            <div className="assistant-content"><h1>{result.response_type === "conversation" ? "Oncology AI" : "Answer"}</h1><CareUrgency review={result.care_urgency} />{result.structured_answer ? <StructuredAnswer answer={result.structured_answer} /> : <><ResearchSummary summary={result.research_summary} /><p className="assistant-summary">{result.summary}</p></>}<details className="advanced-evidence"><summary>Show detailed evidence ({result.research_summary?.related_records || 0})</summary><EvidenceList evidence={result.evidence} supportingImages={result.supporting_image_evidence} uploadedSources={result.uploaded_sources} citationValidation={result.citation_validation} /></details>{!result.structured_answer && <RiskReview review={result.risk_review} />}{result.response_type !== "conversation" && result.disclaimer && <aside className="chat-disclaimer"><strong>Disclaimer:</strong> {result.disclaimer}</aside>}</div>
          </article>}
          {turns.map((turn, index) => <React.Fragment key={`${turn.question}-${index}`}><article className="user-turn"><div><MessageAttachments files={turn.fileName ? [{ name: turn.fileName, previewUrl: turn.previewUrl, kind: turn.previewUrl ? "image" : "report" }] : []} /><p>{turn.question}</p></div></article><article className="assistant-turn compact"><div className="assistant-avatar"><FaHeartbeat /></div><div className="assistant-content"><CareUrgency review={turn.careUrgency} />{turn.structuredAnswer ? <StructuredAnswer answer={turn.structuredAnswer} /> : <p className="assistant-summary">{turn.answer}</p>}<details className="advanced-evidence"><summary>Show detailed evidence</summary><EvidenceList evidence={turn.evidence} supportingImages={turn.supportingImages} uploadedSources={turn.uploadedSources} citationValidation={turn.citationValidation} /></details></div></article></React.Fragment>)}
          {sending && <article className="assistant-turn compact"><div className="assistant-avatar"><FaHeartbeat /></div><div className="assistant-content"><ThinkingIndicator label="Thinking" /></div></article>}
        </div>
        <div className="chat-composer-dock">
          {error && <p className="chat-error">{error}</p>}
          <form className="chat-followup" onSubmit={sendFollowUp}>
            {attachment && <div className="chat-attachment-preview">{attachment.previewUrl ? <img src={attachment.previewUrl} alt={`Preview of ${attachment.name}`} /> : <FaImage />}<span>{attachment.name}</span><button type="button" onClick={removeFollowupAttachment}><FaXmark /></button></div>}
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a follow-up about this report or image…" onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendFollowUp(event); } }} />
            <button className="chat-attach-button" type="button" disabled={uploading || Boolean(attachment)} onClick={() => followupFileRef.current?.click()} aria-label="Upload another file"><FaPaperclip /></button>
            <button type="submit" disabled={initialLoading || (!question.trim() && !attachment) || sending || !activeSessionId} aria-label="Send follow-up"><FaPaperPlane /></button>
            <input ref={followupFileRef} hidden type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={attachAnotherFile} />
          </form>
          <small>Oncology AI may make mistakes. Always consult a qualified medical professional for diagnosis and treatment decisions.</small>
        </div>
      </main>
    </div>
  );
}
