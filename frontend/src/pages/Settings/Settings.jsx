import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import {
  FaArrowLeft,
  FaUser,
  FaLock,
  FaBoxArchive,
  FaRightFromBracket,
  FaChevronRight,
} from "react-icons/fa6";

import "./Settings.css";
import { changePassword } from "../../services/securityService";

export default function Settings() {
  const navigate = useNavigate();
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

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
    </div>
  );
}
