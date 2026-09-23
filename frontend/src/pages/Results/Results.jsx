import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaHeartbeat } from "react-icons/fa";
import { FaArrowRightFromBracket, FaClockRotateLeft, FaFilePdf, FaGear, FaImage, FaPaperclip, FaPaperPlane, FaPlus, FaRegUser, FaXmark } from "react-icons/fa6";
import { analyzeSession, analyzeText, clearConversationCache } from "../../services/analysisService";
import { getUploadHistory, getUploadSession, uploadFiles } from "../../services/uploadService";
import "./Results.css";
import oncologyLogo from "../../assets/oncology-ai-logo.png";

function CareUrgency({ review }) {
  if (!review?.level) return null;
  const indicators = {
    emergency: { symbol: "●", label: "Red urgency indicator" },
    prompt: { symbol: "●", label: "Yellow urgency indicator" },
    routine: { symbol: "●", label: "Blue urgency indicator" },
    insufficient: { symbol: "○", label: "White insufficient-information indicator" },
  };
  const indicator = indicators[review.level] || indicators.insufficient;
  return (
    <section className={`care-urgency urgency-${review.level}`} aria-label="Care urgency guidance">
      <div>
        <span className="urgency-dot" role="img" aria-label={indicator.label}>{indicator.symbol}</span>
        <small>What to do next</small>
        <strong>{review.label}</strong>
      </div>
      <p>{review.message}</p>
      <span>Guidance only · not an emergency diagnosis or cancer-risk probability</span>
    </section>
  );
}

function CaseComplexity({ review }) {
  if (!review?.level) return null;
  const indicators = {
    high: { symbol: "●", label: "Red high-complexity indicator" },
    moderate: { symbol: "●", label: "Orange moderate-complexity indicator" },
    lower: { symbol: "●", label: "Green lower-complexity indicator" },
    insufficient: { symbol: "○", label: "White insufficient-information indicator" },
  };
  const indicator = indicators[review.level] || indicators.insufficient;
  return (
    <section className={`case-complexity complexity-${review.level}`} aria-label="Documented case complexity">
      <div>
        <span className="complexity-dot" role="img" aria-label={indicator.label}>{indicator.symbol}</span>
        <small>Case complexity</small>
        <strong>{review.label}</strong>
      </div>
      <p>{review.message}</p>
      <span>Based on explicit report findings · not a cancer-risk percentage or diagnosis</span>
    </section>
  );
}

export function GenerationStatus({ mode, diagnostics = {} }) {
  if (!mode) return null;
  const labels = {
    gemini_structured: "AI-generated structured interpretation",
    gemini_degraded: "AI-generated degraded interpretation",
    extractive_fallback: "Retrieval-only fallback",
  };
  const quotaReached = Boolean(diagnostics.quota_exhausted);
  return (
    <aside className={`generation-status generation-${mode}`} role="status">
      <strong>{labels[mode] || "Analysis result"}</strong>
      {quotaReached && <p>AI interpretation is temporarily unavailable because the model service quota has been reached. A retrieval-only summary based on the uploaded report is shown instead.</p>}
    </aside>
  );
}

export function EvidenceSupport({ reliability }) {
  if (!reliability?.score && reliability?.score !== 0) return null;
  const components = reliability.components || {};
  const labels = {
    patient_document_support: "Patient-document support",
    retrieval_support: "Retrieved evidence",
    citation_support: "Citation validation",
    evidence_agreement: "Evidence agreement",
    completeness: "Completeness",
  };
  return (
    <section className="reliability-score" aria-label="Evidence support score">
      <div><span><strong>{reliability.score}%</strong><small>Evidence Support</small></span><p><strong>{reliability.label}</strong><small>{reliability.explanation}</small></p></div>
      <details><summary>Why this score?</summary>
        <ul>{(reliability.reasons || []).map((reason) => <li key={reason}>{reason}</li>)}</ul>
        <dl>{Object.entries(components).map(([key, value]) => <div key={key}><dt>{labels[key] || key.replaceAll("_", " ")}</dt><dd>{value}/100</dd></div>)}</dl>
      </details>
    </section>
  );
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const stages = [
    { after: 0, progress: 8, text: "Preparing your clinical material" },
    { after: 3, progress: 18, text: "Loading conversation context" },
    { after: 8, progress: 35, text: "Retrieving relevant oncology evidence" },
    { after: 15, progress: 52, text: "Selecting and loading the analysis prompts" },
    { after: 25, progress: 70, text: "Waiting for the AI analysis service" },
    { after: 45, progress: 84, text: "Checking the response and citations" },
    { after: 60, progress: 90, text: "The service is taking longer than expected" },
  ];
  const stage = [...stages].reverse().find((item) => elapsedSeconds >= item.after) || stages[0];
  const isDelayed = elapsedSeconds >= 30;

  return (
    <div className="chat-thinking-box" role="status" aria-live="polite">
      <span className="chat-thinking-dots" aria-hidden="true"><i /><i /><i /></span>
      <div className="chat-thinking-copy">
        <span className="chat-thinking-heading"><strong>{label}</strong><b>{stage.progress}%</b></span>
        <small>{stage.text}…</small>
        <span className="chat-thinking-progress" aria-label={`Estimated progress ${stage.progress} percent`}>
          <i style={{ width: `${stage.progress}%` }} />
        </span>
        <small className="chat-thinking-meta">
          Estimated progress · {elapsedSeconds}s elapsed
        </small>
        {isDelayed && (
          <p className="chat-thinking-warning">
            Still waiting for the server. A slow connection or busy AI service may be responsible; this request will stop automatically if it times out.
          </p>
        )}
      </div>
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
  // Gemini's richer schema uses key_findings. Keep findings only for older
  // saved analyses and never render both sections as duplicates.
  const findings = asObjectArray((answer.key_findings?.length ? answer.key_findings : answer.findings));
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
            <th scope="row">{displayText(item.title || item.finding)}<CitationTags citations={item.citations} /></th>
            <td>{displayText(item.result)}</td><td>{displayText(item.meaning)}</td>
          </tr>)}</tbody>
        </table></div>
      </section>}

      {answer.staging && (answer.staging.documented_components?.length > 0 || answer.staging.unresolved_components?.length > 0 || answer.staging.final_stage || answer.staging.explanation) && <section className="answer-section">
        <h2>Staging</h2>
        {answer.staging.explanation && <p>{displayText(answer.staging.explanation)}</p>}
        {answer.staging.final_stage && <p><strong>Documented stage:</strong> {displayText(answer.staging.final_stage)}</p>}
        <CitationTags citations={answer.staging.citations} />
      </section>}

      {limitations.length > 0 && <section className="answer-section">
        <h2>Important limitations</h2><div className="evidence-balance">
          <div>{limitations.map((item, index) => <p key={index}>! {item}</p>)}</div>
        </div>
      </section>}

      {medicalTerms.length > 0 && <details className="medical-terms answer-section">
        <summary>Explain the medical terms</summary>
        <div>{medicalTerms.map((item, index) => <article key={`${displayText(item.term)}-${index}`}><strong>{displayText(item.term)}</strong><p>{displayText(item.definition)}</p></article>)}</div>
      </details>}

      {answer.safety_notice && <p className="assistant-summary">{displayText(answer.safety_notice)}</p>}

    </div>
  );
}

export function ResponseContent({ contract, structuredAnswer, summary }) {
  if (contract === "general" && structuredAnswer?.answer) {
    return <div className="conversational-answer"><p className="assistant-summary">{structuredAnswer.answer}</p><CitationTags citations={structuredAnswer.reference_citations} /></div>;
  }
  if (contract === "focused" && structuredAnswer?.answer) {
    return <div className="focused-answer"><p className="assistant-summary">{structuredAnswer.answer}</p><span>{displayText(structuredAnswer.certainty)?.replaceAll("_", " ")}</span><CitationTags citations={structuredAnswer.citations} /></div>;
  }
  return structuredAnswer ? <StructuredAnswer answer={structuredAnswer} /> : <p className="assistant-summary">{summary}</p>;
}

export function inferResponseContract(explicitContract, structuredAnswer) {
  if (explicitContract) return explicitContract;
  if (structuredAnswer?.plain_language_summary || structuredAnswer?.headline || structuredAnswer?.key_findings || structuredAnswer?.findings) return "full_report";
  if (structuredAnswer?.answer && structuredAnswer?.certainty) return "focused";
  if (structuredAnswer?.answer) return "general";
  return null;
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const initial = location.state?.result;
  const pendingAnalysis = location.state?.pendingAnalysis;
  const initialPrompt = pendingAnalysis?.text ?? location.state?.prompt;
  const initialAttachments = pendingAnalysis?.attachments ?? location.state?.attachments ?? [];
  const initialSavedMessages = location.state?.savedMessages ?? [];
  const initialSavedAnalyses = location.state?.savedAnalyses ?? [];
  const [displayedPrompt, setDisplayedPrompt] = useState(initialPrompt || "");
  const [displayedAttachments, setDisplayedAttachments] = useState(initialAttachments);
  const [result, setResult] = useState(initial);
  const [activeSessionId, setActiveSessionId] = useState(initial?.session_id || pendingAnalysis?.sessionId || null);
  const [initialLoading, setInitialLoading] = useState(Boolean(pendingAnalysis && !initial));
  const [turns, setTurns] = useState(() => initialSavedAnalyses.length > 1
    ? initialSavedAnalyses.slice(1).map((analysis) => ({ question: analysis.question, answer: analysis.result?.summary, responseType: analysis.result?.response_type, responseContract: analysis.result?.response_contract, structuredAnswer: analysis.result?.structured_answer, briefResponse: analysis.result?.brief_response, evidence: analysis.result?.evidence, supportingImages: analysis.result?.supporting_image_evidence, uploadedSources: analysis.result?.uploaded_sources, citationValidation: analysis.result?.citation_validation, careUrgency: analysis.result?.care_urgency, caseComplexity: analysis.result?.case_complexity, reliability: analysis.result?.reliability, generationMode: analysis.result?.generation_mode, generationDiagnostics: analysis.result?.generation_diagnostics, fileName: analysis.attachments?.[0]?.name, fileType: analysis.attachments?.[0]?.type, fileKind: analysis.attachments?.[0]?.kind }))
    : initialSavedMessages.slice(1).map((message) => ({ question: message.question, answer: message.answer, responseType: "conversation" })));
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [attachment, setAttachment] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const followupFileRef = useRef(null);
  const initialRequestStarted = useRef(false);

  useEffect(() => {
    if (!pendingAnalysis || initial || initialRequestStarted.current) return;
    initialRequestStarted.current = true;
    const controller = new AbortController();
    let active = true;
    const runInitialAnalysis = async () => {
      setInitialLoading(true);
      setError("");
      try {
        const next = pendingAnalysis.sessionId
          ? await analyzeSession(pendingAnalysis.sessionId, pendingAnalysis.text || "", 5, controller.signal)
          : await analyzeText(pendingAnalysis.text || "", 5, controller.signal);
        setResult(next);
        setActiveSessionId(next.session_id);
        setError("");
        navigate("/results", {
          replace: true,
          state: {
            result: next,
            prompt: pendingAnalysis.text || "Analyze this uploaded file",
            attachments: pendingAnalysis.attachments || [],
          },
        });
      } catch (requestError) {
        if (requestError.code === "ERR_CANCELED") return;
        const message = requestError.response?.data?.detail || requestError.message || "Analysis failed.";
        const rejection = {
          session_id: pendingAnalysis.sessionId || null,
          response_type: "rejection",
          query_type: "validation",
          summary: message,
        };
        setResult(rejection);
        if (pendingAnalysis.sessionId) setActiveSessionId(pendingAnalysis.sessionId);
        setError("");
        navigate("/results", {
          replace: true,
          state: {
            result: rejection,
            prompt: pendingAnalysis.text || "Analyze this uploaded file",
            attachments: pendingAnalysis.attachments || [],
          },
        });
      } finally {
        if (active) setInitialLoading(false);
      }
    };
    runInitialAnalysis();
    return () => {
      active = false;
      controller.abort();
      initialRequestStarted.current = false;
    };
  }, [initial, navigate, pendingAnalysis]);

  useEffect(() => {
    const email = localStorage.getItem("email");
    if (!email) return;
    getUploadHistory(email).then((items) => setRecentAnalyses(items)).catch(() => setRecentAnalyses([]));
  }, [turns, result?.session_id, result?.summary]);

  const attachAnotherFile = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setUploading(true); setUploadProgress(0); setError("");
    try {
      const response = await uploadFiles(localStorage.getItem("email"), files, activeSessionId, setUploadProgress);
      const file = files[0];
      setAttachment({ sessionId: response.session_id, name: file.name, type: file.type, kind: file.type.startsWith("image/") ? "image" : "report", previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null });
    } catch (requestError) { setError(requestError.response?.data?.detail || "Unable to upload file."); }
    finally { setUploading(false); setUploadProgress(0); event.target.value = ""; }
  };

  const removeFollowupAttachment = async () => {
    if (!attachment) return;
    const removed = attachment;
    setAttachment(null);
    if (removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
  };

  const openRecent = async (sessionId) => {
    if (sessionId === activeSessionId) {
      setError("");
      return;
    }
    try {
      const session = await getUploadSession(sessionId);
      const messages = session.messages || [];
      const saved = session.analyses?.[0]?.result || (session.input_type === "text" && messages.length
        ? { response_type: "conversation", query_type: "conversation", summary: messages[0].answer }
        : session.latest_summary?.result || (session.failure_reason ? { response_type: "rejection", query_type: "validation", summary: session.failure_reason } : null));
      if (!saved) throw new Error("This analysis is not complete.");
      setResult({ session_id: sessionId, ...saved });
      setActiveSessionId(sessionId);
      setDisplayedPrompt(session.analyses?.[0]?.question || session.original_query || "Analyze this uploaded file");
      setDisplayedAttachments(session.analyses?.[0]?.attachments || [
        ...(session.reports || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "report" })),
        ...(session.images || []).map((file) => ({ name: file.file_name, type: file.mime_type, kind: "image" })),
      ]);
      setTurns(session.analyses?.length > 1 ? session.analyses.slice(1).map((analysis) => ({
        question: analysis.question,
        answer: analysis.result?.summary,
        responseType: analysis.result?.response_type,
        responseContract: analysis.result?.response_contract,
        structuredAnswer: analysis.result?.structured_answer,
        briefResponse: analysis.result?.brief_response,
        evidence: analysis.result?.evidence,
        supportingImages: analysis.result?.supporting_image_evidence,
        uploadedSources: analysis.result?.uploaded_sources,
        citationValidation: analysis.result?.citation_validation,
        careUrgency: analysis.result?.care_urgency,
        caseComplexity: analysis.result?.case_complexity,
        fileName: analysis.attachments?.[0]?.name,
        fileType: analysis.attachments?.[0]?.type,
        fileKind: analysis.attachments?.[0]?.kind,
      })) : messages.slice(1).map((message) => ({
        question: message.question,
        answer: message.answer,
        responseType: "conversation",
      })));
      setError(""); setAttachment(null); window.scrollTo({ top: 0, behavior: "smooth" });
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
    const submittedAttachment = attachment;
    const pendingId = `${Date.now()}-${Math.random()}`;
    const pendingTurn = { id: pendingId, question: clean || "Analyze this uploaded file", answer: null, pending: true, previewUrl: submittedAttachment?.previewUrl, fileName: submittedAttachment?.name, fileType: submittedAttachment?.type, fileKind: submittedAttachment?.kind };
    setQuestion(""); setError(""); setAttachment(null); setSending(true);
    setTurns((current) => [...current, pendingTurn]);
    window.setTimeout(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }), 0);
    try {
      const next = await analyzeSession(activeSessionId, clean);
      setTurns((current) => current.map((turn) => turn.id === pendingId ? { ...turn, pending: false, answer: next.summary, responseType: next.response_type, responseContract: next.response_contract, structuredAnswer: next.structured_answer, briefResponse: next.brief_response, evidence: next.evidence, supportingImages: next.supporting_image_evidence, uploadedSources: next.uploaded_sources, citationValidation: next.citation_validation, careUrgency: next.care_urgency, caseComplexity: next.case_complexity, reliability: next.reliability, generationMode: next.generation_mode, generationDiagnostics: next.generation_diagnostics } : turn));
      setResult((current) => ({ ...current, session_id: activeSessionId }));
      window.setTimeout(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }), 0);
    } catch (requestError) {
      const message = requestError.response?.data?.detail || "Unable to answer the follow-up question.";
      setTurns((current) => current.map((turn) => turn.id === pendingId ? { ...turn, pending: false, answer: message, responseType: "rejection", isError: true } : turn));
    } finally { setSending(false); }
  };

  const resultContract = inferResponseContract(result?.response_contract, result?.structured_answer);

  return (
    <div className="chat-workspace">
      <aside className="chat-sidebar">
        <div className="chat-brand"><span><img src={oncologyLogo} alt="Oncology AI logo" /></span><div><strong>Oncology AI</strong><small>Clinical Intelligence</small></div></div>
        <button className="chat-new" onClick={() => navigate("/dashboard")}><FaPlus /> New analysis</button>
        <nav><button onClick={() => navigate("/dashboard")}><FaHeartbeat /> Assistant</button><button onClick={() => navigate("/history")}><FaClockRotateLeft /> History</button><button onClick={() => navigate("/profile")}><FaRegUser /> Profile</button><button onClick={() => navigate("/settings")}><FaGear /> Settings</button></nav>
        <section className="chat-recents"><h2>Recents</h2><div className="chat-recents-list">{recentAnalyses.length === 0 ? <p>No saved analyses yet.</p> : recentAnalyses.map((item) => <button className={item.session_id === activeSessionId ? "active" : ""} key={item.session_id} disabled={item.status !== "Completed" && item.session_id !== activeSessionId} onClick={() => openRecent(item.session_id)}>{item.display_title || item.session_name}</button>)}</div></section>
        <p className="chat-sidebar-note">Clinical decision support only</p>
        <button className="chat-logout" onClick={() => { localStorage.clear(); navigate("/"); }}><FaArrowRightFromBracket /> Logout</button>
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
          {initialLoading && <article className="assistant-turn compact"><div className="assistant-avatar"><img src={oncologyLogo} alt="" /></div><div className="assistant-content"><ThinkingIndicator label="Reviewing your clinical material" /></div></article>}
          {result && <article className="assistant-turn">
            <div className="assistant-avatar"><img src={oncologyLogo} alt="Oncology AI" /></div>
            <div className="assistant-content"><h1>{result.response_type === "conversation" ? "Oncology AI" : result.response_type === "rejection" ? "Upload needs attention" : "Answer"}</h1><GenerationStatus mode={result.generation_mode} diagnostics={result.generation_diagnostics} /><EvidenceSupport reliability={result.reliability} />{resultContract === "full_report" && <CaseComplexity review={result.case_complexity} />}{(resultContract === "full_report" || result.care_urgency?.level === "emergency") && <CareUrgency review={result.care_urgency} />}<ResponseContent contract={resultContract} structuredAnswer={result.structured_answer} summary={result.summary} />{resultContract === "full_report" && result.response_type !== "rejection" && ((result.evidence?.length || 0) + (result.supporting_image_evidence?.length || 0) + (result.uploaded_sources?.length || 0) > 0) && <details className="advanced-evidence"><summary>Show detailed evidence ({result.research_summary?.related_records || 0})</summary><EvidenceList evidence={result.evidence} supportingImages={result.supporting_image_evidence} uploadedSources={result.uploaded_sources} citationValidation={result.citation_validation} /></details>}</div>
          </article>}
          {turns.map((turn, index) => { const turnContract = inferResponseContract(turn.responseContract, turn.structuredAnswer); return <React.Fragment key={turn.id || `${turn.question}-${index}`}><article className="user-turn"><div><MessageAttachments files={turn.fileName ? [{ name: turn.fileName, previewUrl: turn.previewUrl, type: turn.fileType, kind: turn.fileKind }] : []} /><p>{turn.question}</p></div></article><article className={`assistant-turn compact ${turn.isError ? "assistant-notice" : ""}`}><div className="assistant-avatar"><img src={oncologyLogo} alt="Oncology AI" /></div><div className="assistant-content">{turn.pending ? <ThinkingIndicator label="Thinking" /> : <><GenerationStatus mode={turn.generationMode} diagnostics={turn.generationDiagnostics} /><EvidenceSupport reliability={turn.reliability} />{turnContract === "full_report" && <CaseComplexity review={turn.caseComplexity} />}{(turnContract === "full_report" || turn.careUrgency?.level === "emergency") && <CareUrgency review={turn.careUrgency} />}<ResponseContent contract={turnContract} structuredAnswer={turn.structuredAnswer} summary={turn.answer} />{turnContract === "full_report" && turn.responseType !== "rejection" && ((turn.evidence?.length || 0) + (turn.supportingImages?.length || 0) + (turn.uploadedSources?.length || 0) > 0) && <details className="advanced-evidence"><summary>Show detailed evidence</summary><EvidenceList evidence={turn.evidence} supportingImages={turn.supportingImages} uploadedSources={turn.uploadedSources} citationValidation={turn.citationValidation} /></details>}</>}</div></article></React.Fragment>; })}
          {error && <article className="assistant-turn compact assistant-notice"><div className="assistant-avatar"><img src={oncologyLogo} alt="Oncology AI" /></div><div className="assistant-content"><h2>Unable to complete the request</h2><p className="assistant-summary">{error}</p></div></article>}
          {!initialLoading && !sending && (result || turns.length > 0 || error) && <aside className="conversation-caution"><strong>Caution</strong><span>AI-generated answers may be incomplete or incorrect. Please verify important medical information with a qualified healthcare professional.</span></aside>}
        </div>
        <div className="chat-composer-dock">
          <form className="chat-followup" onSubmit={sendFollowUp}>
            {uploading && <div className="upload-progress" role="status" aria-live="polite"><div className="upload-progress-label"><span>Uploading file</span><strong>{uploadProgress}%</strong></div><div className="upload-progress-track"><i style={{ width: `${uploadProgress}%` }} /></div></div>}
            {attachment && <div className="chat-attachment-preview">{attachment.previewUrl ? <img src={attachment.previewUrl} alt={`Preview of ${attachment.name}`} /> : <FaImage />}<span>{attachment.name}</span><button type="button" onClick={removeFollowupAttachment}><FaXmark /></button></div>}
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a follow-up about this report or image…" onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendFollowUp(event); } }} />
            <button className="chat-attach-button" type="button" disabled={uploading || Boolean(attachment)} onClick={() => followupFileRef.current?.click()} aria-label="Upload another file"><FaPaperclip /></button>
            <button type="submit" disabled={initialLoading || (!question.trim() && !attachment) || sending || !activeSessionId} aria-label="Send follow-up"><FaPaperPlane /></button>
            <input ref={followupFileRef} hidden type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={attachAnotherFile} />
          </form>
        </div>
      </main>
    </div>
  );
}
