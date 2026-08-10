import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaHeartbeat } from "react-icons/fa";
import { analyzeSession, analyzeText } from "../../services/analysisService";
import "./Processing.css";

export default function Processing() {
  const location = useLocation();
  const navigate = useNavigate();
  const started = useRef(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const run = async () => {
      try {
        const { sessionId, text, attachments } = location.state || {};
        if (!sessionId && !text) throw new Error("No analysis input was provided.");
        const result = sessionId
          ? await analyzeSession(sessionId, text || "")
          : await analyzeText(text);
        navigate("/results", {
          replace: true,
          state: { result, prompt: text || "Analyze this uploaded file", attachments: attachments || [] },
        });
      } catch (requestError) {
        setError(
          requestError.response?.data?.detail ||
            requestError.message ||
            "Analysis failed."
        );
      }
    };
    run();
  }, [location.state, navigate]);

  return (
    <main className="processing-page">
      <section className="processing-card">
        <div className="processing-icon"><FaHeartbeat /></div>
        {error ? (
          <>
            <h1>Analysis could not be completed</h1>
            <p className="processing-error">{error}</p>
            <button type="button" onClick={() => navigate("/dashboard")}>Return to dashboard</button>
          </>
        ) : (
          <>
            <h1>Reviewing your clinical material</h1>
            <p>Encoding the input, retrieving similar oncology evidence, and preparing a grounded summary.</p>
            <div className="processing-loader" aria-label="Analysis in progress" />
            <small>The first request can take longer while the medical models load.</small>
          </>
        )}
      </section>
    </main>
  );
}
