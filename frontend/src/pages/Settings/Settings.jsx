import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import {
  FaArrowLeft,
  FaUser,
  FaLock,
  FaKey,
  FaBoxArchive,
  FaRightFromBracket,
  FaChevronRight,
} from "react-icons/fa6";

import "./Settings.css";
import { changePassword } from "../../services/securityService";
import api from "../../services/api";

export default function Settings() {
  const navigate = useNavigate();
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [pinOpen, setPinOpen] = useState(false);
  const [pinPassword, setPinPassword] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [pinError, setPinError] = useState("");
  const [pinSuccess, setPinSuccess] = useState("");
  const [savingPin, setSavingPin] = useState(false);

  const handleLogout = () => {
    localStorage.clear();
    navigate("/");
  };

  const submitPassword = async (event) => {
    event.preventDefault();
    setPasswordError("");
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("New password must contain at least 8 characters.");
      return;
    }
    setSavingPassword(true);
    try {
      await changePassword(oldPassword, newPassword);
      localStorage.clear();
      navigate("/", { replace: true, state: { message: "Password changed. Sign in with your new password." } });
    } catch (error) {
      setPasswordError(error.response?.data?.detail || "Unable to change password.");
    } finally { setSavingPassword(false); }
  };

  const submitPin = async (event) => {
    event.preventDefault(); setPinError(""); setPinSuccess("");
    if (!/^(?:\d{4}|\d{6})$/.test(newPin)) return setPinError("PIN must contain exactly 4 or 6 digits.");
    if (newPin !== confirmPin) return setPinError("Recovery PINs do not match.");
    setSavingPin(true);
    try {
      const response = await api.post("/auth/change-recovery-pin", {
        current_password: pinPassword, new_recovery_pin: newPin,
      });
      setPinSuccess(response.data.message); setPinPassword(""); setNewPin(""); setConfirmPin("");
    } catch (error) {
      setPinError(error.response?.data?.detail || "Unable to change recovery PIN.");
    } finally { setSavingPin(false); }
  };

  return (
    <div className="settings-page">
      <motion.div
        className="settings-card"
        initial={{ opacity: 0, y: 25 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="settings-header">
          <button
            className="back-btn"
            onClick={() => navigate("/dashboard")}
          >
            <FaArrowLeft />
          </button>

          <h1>Settings</h1>
        </div>

        <div className="settings-list">

          <button
            className="settings-item"
            onClick={() => navigate("/profile?from=settings")}
          >
            <div>
              <FaUser />
              <span>My Profile</span>
            </div>

            <FaChevronRight />
          </button>

          <button
            className="settings-item"
            onClick={() => setPasswordOpen(true)}
          >
            <div>
              <FaLock />
              <span>Change Password</span>
            </div>

            <FaChevronRight />
          </button>

          <button className="settings-item" onClick={() => { setPinOpen(true); setPinError(""); setPinSuccess(""); }}>
            <div><FaKey /><span>Change Recovery PIN</span></div>
            <FaChevronRight />
          </button>

          <button
            className="settings-item"
            onClick={() => navigate("/archive")}
          >
            <div>
              <FaBoxArchive />
              <span>Archive</span>
            </div>

            <FaChevronRight />
          </button>

          <button
            className="settings-item logout"
            onClick={handleLogout}
          >
            <div>
              <FaRightFromBracket />
              <span>Logout</span>
            </div>
          </button>

        </div>
      </motion.div>
      {passwordOpen && (
        <div className="settings-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setPasswordOpen(false); }}>
          <section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="change-password-title">
            <h2 id="change-password-title">Change Password</h2>
            <p>Confirm your current password, then choose a new password.</p>
            <form onSubmit={submitPassword}>
              <label>Current password<input type="password" autoComplete="current-password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} required /></label>
              <label>New password<input type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} minLength="8" required /></label>
              <label>Confirm new password<input type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength="8" required /></label>
              {passwordError && <div className="settings-password-error" role="alert">{passwordError}</div>}
              <div className="settings-modal-actions"><button type="button" onClick={() => setPasswordOpen(false)}>Cancel</button><button type="submit" disabled={savingPassword}>{savingPassword ? "Saving…" : "Save password"}</button></div>
            </form>
          </section>
        </div>
      )}
      {pinOpen && (
        <div className="settings-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setPinOpen(false); }}>
          <section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="change-pin-title">
            <h2 id="change-pin-title">Change Recovery PIN</h2>
            <p>Confirm your current password, then choose a new 4- or 6-digit recovery PIN.</p>
            <form onSubmit={submitPin}>
              <label>Current password<input type="password" autoComplete="current-password" value={pinPassword} onChange={(event) => setPinPassword(event.target.value)} required /></label>
              <label>New recovery PIN<input type="password" inputMode="numeric" autoComplete="off" value={newPin} onChange={(event) => setNewPin(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="4 or 6 digits" required /></label>
              <label>Confirm recovery PIN<input type="password" inputMode="numeric" autoComplete="off" value={confirmPin} onChange={(event) => setConfirmPin(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="Re-enter PIN" required /></label>
              {pinError && <div className="settings-password-error" role="alert">{pinError}</div>}
              {pinSuccess && <div className="settings-pin-success" role="status">{pinSuccess}</div>}
              <div className="settings-modal-actions"><button type="button" onClick={() => setPinOpen(false)}>Cancel</button><button type="submit" disabled={savingPin}>{savingPin ? "Saving…" : "Save PIN"}</button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
