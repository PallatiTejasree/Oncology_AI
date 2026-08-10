import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  FaArrowRight,
  FaClipboardList,
  FaEye,
  FaEyeSlash,
  FaLock,
  FaRobot,
  FaShieldAlt,
  FaUser,
  FaXRay,
} from "react-icons/fa";
import oncologyLogo from "../../assets/oncology-ai-logo.png";
import "./Login.css";

const stats = [
  { icon: FaXRay, value: "3072+", label: "Medical Images" },
  { icon: FaClipboardList, value: "3072+", label: "Clinical Reports" },
  { icon: FaRobot, value: "AI", label: "Smart Retrieval" },
  { icon: FaShieldAlt, value: "100%", label: "Secure Access" },
];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post("http://127.0.0.1:8000/auth/login", {
        email,
        password,
      });

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
            {stats.map(({ icon: Icon, value, label }) => (
              <article key={label} className="login-stat-card">
                <div className="login-stat-heading">
                  <Icon aria-hidden="true" />
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
          <p className="login-subtitle">Sign in or create your workspace automatically</p>

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
                  autoComplete="current-password"
                  placeholder="Enter Password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={6}
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

            <button
              type="button"
              className="login-forgot"
              onClick={() => navigate("/forgot-password")}
            >
              Forgot Password?
            </button>

            {error && (
              <div className="login-error" role="alert">
                {error}
              </div>
            )}

            <button type="submit" className="login-submit" disabled={loading}>
              <span>{loading ? "Continuing..." : "Continue"}</span>
              <FaArrowRight aria-hidden="true" />
            </button>
          </form>

          <p className="login-security">Secure • AI Powered • Enterprise Ready</p>
          <p className="login-register login-auto-account">
            New email? We will securely create your account automatically.
          </p>
        </motion.section>
      </div>
    </main>
  );
}
