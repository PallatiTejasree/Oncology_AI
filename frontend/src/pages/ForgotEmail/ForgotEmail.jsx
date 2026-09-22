import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaEnvelopeOpenText, FaKey, FaShieldAlt } from "react-icons/fa";
import api from "../../services/api";
import "../ForgotPassword/ForgotPassword.css";

export default function ForgotEmail() {
  const navigate = useNavigate();
  const [pin, setPin] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault(); setError(""); setEmail("");
    if (!/^(?:\d{4}|\d{6})$/.test(pin)) return setError("Enter your 4- or 6-digit recovery PIN.");
    setLoading(true);
    try {
      const response = await api.post("/auth/forgot-email", { recovery_pin: pin });
      setEmail(response.data.email);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to recover email.");
    } finally { setLoading(false); }
  };

  return <main className="login-page forgot-page">
    <div className="login-glow login-glow-left" aria-hidden="true" />
    <div className="login-glow login-glow-right" aria-hidden="true" />
    <section className="login-form-card recovery-card">
      <button className="recovery-back" type="button" onClick={() => navigate("/")}><FaArrowLeft /> Back to sign in</button>
      <div className="recovery-hero">
        <span className="recovery-hero-icon"><FaEnvelopeOpenText /></span>
        <small>ACCOUNT RECOVERY</small>
        <h2>Find your email</h2>
        <p>Enter the private recovery PIN you created when signing up.</p>
      </div>
      <form onSubmit={submit}>
        <div className="login-field"><label>Recovery PIN</label><div className="login-input-wrap"><FaKey /><input
          type="password" inputMode="numeric" value={pin} placeholder="4 or 6 digits"
          onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 6))} required /></div></div>
        {error && <p className="login-error" role="alert">{error}</p>}
        {email && <div className="recovered-email"><small>Your registered email</small><strong>{email}</strong><button type="button" onClick={() => navigate("/forgot-password")}>Reset password</button></div>}
        <button className="login-submit" type="submit" disabled={loading}>{loading ? "Checking..." : "Recover Email"}</button>
      </form>
      <div className="recovery-trust"><span><FaShieldAlt /> PIN protected</span></div>
    </section>
  </main>;
}
