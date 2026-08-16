import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaArrowRight, FaEnvelope, FaLock } from "react-icons/fa";
import api from "../../services/api";
import "./ForgotPassword.css";

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const submit = async (event) => {
    event.preventDefault(); setError(""); setSuccess("");
    if (!/^(?:\d{4}|\d{6})$/.test(pin)) return setError("Enter your 4- or 6-digit recovery PIN.");
    if (password.length < 8) return setError("Password must contain at least 8 characters.");
    if (password !== confirm) return setError("Passwords do not match.");
    setLoading(true);
    try {
      const response = await api.post("/auth/forgot-password", {
        email, recovery_pin: pin, new_password: password,
      });
      setSuccess(response.data.message);
      window.setTimeout(() => navigate("/"), 1600);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to reset password.");
    } finally { setLoading(false); }
  };

  return <main className="login-page forgot-page">
    <div className="login-glow login-glow-left" aria-hidden="true" />
    <div className="login-glow login-glow-right" aria-hidden="true" />
    <section className="login-form-card recovery-card">
      <button className="recovery-back" type="button" onClick={() => navigate("/")}><FaArrowLeft /> Back to sign in</button>
      <h2>Reset Password</h2>
      <p className="login-subtitle">Verify your email and recovery PIN, then choose a new password.</p>
      <form onSubmit={submit}>
        <RecoveryField label="Email" icon={<FaEnvelope />} type="email" value={email} onChange={setEmail} placeholder="Enter registered email" />
        <RecoveryField label="Recovery PIN" icon={<FaLock />} type="password" value={pin}
          onChange={(value) => setPin(value.replace(/\D/g, "").slice(0, 6))} placeholder="4 or 6 digits" inputMode="numeric" />
        <RecoveryField label="New Password" icon={<FaLock />} type="password" value={password} onChange={setPassword} placeholder="At least 8 characters" />
        <RecoveryField label="Confirm Password" icon={<FaLock />} type="password" value={confirm} onChange={setConfirm} placeholder="Re-enter password" />
        {error && <p className="login-error" role="alert">{error}</p>}
        {success && <p className="recovery-success">{success}</p>}
        <button className="login-submit" type="submit" disabled={loading}><span>{loading ? "Updating..." : "Reset Password"}</span><FaArrowRight /></button>
      </form>
    </section>
  </main>;
}

function RecoveryField({ label, icon, type, value, onChange, placeholder, inputMode }) {
  return <div className="login-field"><label>{label}</label><div className="login-input-wrap">{icon}<input
    type={type} value={value} inputMode={inputMode} placeholder={placeholder}
    onChange={(event) => onChange(event.target.value)} required /></div></div>;
}
