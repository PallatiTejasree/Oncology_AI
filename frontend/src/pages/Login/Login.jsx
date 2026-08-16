import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  FaArrowRight,
  FaEye,
  FaEyeSlash,
  FaLock,
  FaUser,
} from "react-icons/fa";
import oncologyLogo from "../../assets/oncology-ai-logo.png";
import "./Login.css";

const stats = [
  { emoji: "🩻", value: "206K+", label: "Indexed Medical Images" },
  { emoji: "📚", value: "75K+", label: "Clinical Evidence Passages" },
  { emoji: "🧠", value: "Multimodal", label: "Text + Image Evidence Retrieval" },
  { emoji: "🔐", value: "Private", label: "Session-Scoped Search" },
];

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [recoveryPin, setRecoveryPin] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    if (mode === "signup") {
      if (password.length < 8) {
        setLoading(false);
        setError("Password must contain at least 8 characters.");
        return;
      }
      if (password !== confirmPassword) {
        setLoading(false);
        setError("Passwords do not match.");
        return;
      }
      if (!/^(?:\d{4}|\d{6})$/.test(recoveryPin)) {
        setLoading(false);
        setError("Recovery PIN must contain exactly 4 or 6 digits.");
        return;
      }
    }

    try {
      const response = await axios.post(
        `http://127.0.0.1:8000/auth/${mode === "signup" ? "register" : "login"}`,
        mode === "signup"
          ? { email, password, recovery_pin: recoveryPin }
          : { email, password }
      );

      localStorage.setItem("email", response.data.email);
      localStorage.setItem("access_token", response.data.access_token);
      localStorage.setItem("user", JSON.stringify(response.data));

      navigate(response.data.profile_completed ? "/dashboard" : "/complete-profile");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page">
      <div className="login-glow login-glow-left" aria-hidden="true" />
      <div className="login-glow login-glow-right" aria-hidden="true" />

      <div className="login-layout">
        <motion.section
          className="login-intro"
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7 }}
        >
          <div className="login-brand">
            <div className="login-brand-mark"><img src={oncologyLogo} alt="Oncology AI logo" /></div>
            <div>
              <h2>Oncology AI</h2>
              <p>Enterprise Clinical Intelligence</p>
            </div>
          </div>

          <h1 className="login-hero-title">
            Intelligence<br />
            for Better<br />
            Outcomes.
          </h1>

          <p className="login-description">
            Discover clinical insights faster using AI-powered retrieval for
            pathology reports, medical images, oncology research and
            evidence-based medicine.
          </p>

          <div className="login-stats">
            {stats.map(({ emoji, value, label }) => (
              <article key={label} className="login-stat-card">
                <div className="login-stat-heading">
                  <span className="login-stat-emoji" aria-hidden="true">{emoji}</span>
                  <strong>{value}</strong>
                </div>
                <p>{label}</p>
              </article>
            ))}
          </div>
        </motion.section>

        <motion.section
          className="login-form-card"
          aria-labelledby="login-heading"
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7 }}
        >
          <h2 id="login-heading">Welcome</h2>
          <div className="login-mode-switch" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={mode === "login"}
              className={mode === "login" ? "active" : ""}
              onClick={() => { setMode("login"); setError(""); }}>Sign In</button>
            <button type="button" role="tab" aria-selected={mode === "signup"}
              className={mode === "signup" ? "active" : ""}
              onClick={() => { setMode("signup"); setError(""); }}>Sign Up</button>
          </div>
          <p className="login-subtitle">
            {mode === "login" ? "Sign in to your clinical workspace" : "Create your private clinical workspace"}
          </p>

          <form onSubmit={handleLogin}>
            <div className="login-field">
              <label htmlFor="login-email">Email</label>
              <div className="login-input-wrap">
                <FaUser aria-hidden="true" />
                <input
                  id="login-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="Enter Email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="login-password">Password</label>
              <div className="login-input-wrap">
                <FaLock aria-hidden="true" />
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  placeholder="Enter Password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <FaEyeSlash /> : <FaEye />}
                </button>
              </div>
            </div>

            {mode === "signup" && <>
              <div className="login-field">
                <label htmlFor="login-confirm-password">Confirm Password</label>
                <div className="login-input-wrap">
                  <FaLock aria-hidden="true" />
                  <input id="login-confirm-password" type={showPassword ? "text" : "password"}
                    autoComplete="new-password" placeholder="Re-enter Password"
                    value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
                </div>
              </div>
              <div className="login-field">
                <label htmlFor="recovery-pin">Recovery PIN</label>
                <div className="login-input-wrap">
                  <FaLock aria-hidden="true" />
                  <input id="recovery-pin" type="password" inputMode="numeric"
                    autoComplete="off" placeholder="Choose 4 or 6 digits"
                    value={recoveryPin}
                    onChange={(event) => setRecoveryPin(event.target.value.replace(/\D/g, "").slice(0, 6))}
                    pattern="(?:[0-9]{4}|[0-9]{6})" required />
                </div>
                <small className="login-field-help">Save this PIN securely. It can recover your email or password.</small>
              </div>
            </>}

            {mode === "login" && <div className="login-recovery-links">
              <button type="button" onClick={() => navigate("/forgot-email")}>Forgot Email?</button>
              <button type="button" onClick={() => navigate("/forgot-password")}>Forgot Password?</button>
            </div>}

            {error && (
              <div className="login-error" role="alert">
                {error}
              </div>
            )}

            <button type="submit" className="login-submit" disabled={loading}>
              <span>{loading ? "Please wait..." : mode === "signup" ? "Create Account" : "Sign In"}</span>
              <FaArrowRight aria-hidden="true" />
            </button>
          </form>

          <p className="login-security">Secure • AI Powered • Enterprise Ready</p>
          <p className="login-register login-auto-account">
            {mode === "signup" ? "Already registered? Switch to Sign In above." : "New here? Switch to Sign Up above."}
          </p>
        </motion.section>
      </div>
    </main>
  );
}
