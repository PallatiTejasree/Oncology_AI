import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import {
  FaArrowRightFromBracket,
  FaClockRotateLeft,
  FaGear,
  FaImage,
  FaMessage,
  FaPaperPlane,
  FaPlus,
  FaRegImage,
  FaRegUser,
  FaShieldHalved,
  FaXmark,
} from "react-icons/fa6";


import { deleteUploadSession, getUploadHistory, uploadFiles } from "../../services/uploadService";

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

export default function Dashboard() {
  const navigate = useNavigate();

  const fileInputRef = useRef(null);

  const [message, setMessage] = useState("");

  const [uploading, setUploading] = useState(false);
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [uploadSessionId, setUploadSessionId] = useState(null);

  useEffect(() => {
    const email = localStorage.getItem("email");
    if (!email) return;
    getUploadHistory(email)
      .then((items) => setRecentAnalyses(items.slice(0, 3)))
      .catch(() => setRecentAnalyses([]));
  }, []);

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
    const files = Array.from(event.target.files);

    if (!files.length) return;

    setUploading(true);

    try {
      const email = localStorage.getItem("email");

      const response = await uploadFiles(
        email,
        files
      );

      setUploadSessionId(response.session_id);
      setAttachedFiles(files.map((file) => ({
        name: file.name,
        size: file.size,
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
            <button key={item.session_id} type="button" onClick={() => navigate("/history")}>
              {item.display_title || item.session_name}
            </button>
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

    </div>
  );
}
