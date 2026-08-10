import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaArrowRight, FaEye, FaEyeSlash, FaLock, FaUser } from "react-icons/fa";

import { registerUser } from "../../services/auth";
import "../Login/Login.css";
import "./Register.css";
import oncologyLogo from "../../assets/oncology-ai-logo.png";

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRegister = async (event) => {
    event.preventDefault();
    setError("");

    if (password.length < 6) {
      setError("Password must contain at least 6 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const account = await registerUser(email.trim(), password);
      localStorage.setItem("email", account.email);
      localStorage.setItem("access_token", account.access_token);
      localStorage.setItem("user", JSON.stringify(account));
      navigate("/complete-profile", { replace: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Account creation failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page register-page">
      <div className="login-glow login-glow-left" aria-hidden="true" />
      <div className="login-glow login-glow-right" aria-hidden="true" />
      <motion.section
        className="login-form-card register-card"
        aria-labelledby="register-heading"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <button className="register-back" type="button" onClick={() => navigate("/")}>
          <FaArrowLeft /> Back to sign in
        </button>
        <div className="register-brand"><img src={oncologyLogo} alt="Oncology AI logo" /></div>
        <h2 id="register-heading">Create Account</h2>
        <p className="login-subtitle">Register for your private clinical workspace</p>

        <form onSubmit={handleRegister}>
          <div className="login-field">
            <label htmlFor="register-email">Email</label>
            <div className="login-input-wrap">
              <FaUser aria-hidden="true" />
              <input id="register-email" type="email" autoComplete="email" value={email}
                onChange={(event) => setEmail(event.target.value)} placeholder="Enter Email" required />
            </div>
          </div>

          <div className="login-field">
            <label htmlFor="register-password">Password</label>
            <div className="login-input-wrap">
              <FaLock aria-hidden="true" />
              <input id="register-password" type={showPassword ? "text" : "password"}
                autoComplete="new-password" value={password}
                onChange={(event) => setPassword(event.target.value)} placeholder="At least 6 characters" required />
              <button type="button" className="login-password-toggle"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "Hide password" : "Show password"}>
                {showPassword ? <FaEyeSlash /> : <FaEye />}
              </button>
            </div>
          </div>

          <div className="login-field">
            <label htmlFor="register-confirm-password">Confirm Password</label>
            <div className="login-input-wrap">
              <FaLock aria-hidden="true" />
              <input id="register-confirm-password" type={showPassword ? "text" : "password"}
                autoComplete="new-password" value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Re-enter Password" required />
            </div>
          </div>

          {error && <div className="login-error" role="alert">{error}</div>}
          <button type="submit" className="login-submit" disabled={loading}>
            <span>{loading ? "Creating Account..." : "Create Account"}</span>
            <FaArrowRight aria-hidden="true" />
          </button>
        </form>
        <p className="login-security">Your account is created securely in the application database</p>
      </motion.section>
    </main>
  );
}
