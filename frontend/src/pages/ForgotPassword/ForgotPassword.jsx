import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import axios from "axios";

import {
  FaLock,
  FaEnvelope,
  FaEye,
  FaEyeSlash,
  FaArrowRight,
  FaArrowLeft,
  FaRobot,
  FaClipboardList,
  FaXRay,
  FaShieldAlt,
} from "react-icons/fa";

import "./ForgotPassword.css";
import oncologyLogo from "../../assets/oncology-ai-logo.png";

const stats = [
  { icon: FaXRay, value: "3072+", label: "Medical Images" },
  { icon: FaClipboardList, value: "3072+", label: "Clinical Reports" },
  { icon: FaRobot, value: "AI", label: "Smart Retrieval" },
  { icon: FaShieldAlt, value: "100%", label: "Secure Access" },
];

export default function ForgotPassword() {

  const navigate = useNavigate();

  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  const [confirmPassword, setConfirmPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const [success, setSuccess] = useState("");

  const handleReset = async (e) => {

    e.preventDefault();

    setError("");
    setSuccess("");

    if (password !== confirmPassword) {

      setError("Passwords do not match.");

      return;

    }

    setLoading(true);

    try {

      const response = await axios.post(
        "http://127.0.0.1:8000/auth/forgot-password",
        {
          email,
          new_password: password,
        }
      );

      setSuccess(response.data.message);

      setTimeout(() => {

        navigate("/");

      }, 2000);

    } catch (err) {

      setError(
        err.response?.data?.detail ||
          "Unable to reset password."
      );

    } finally {

      setLoading(false);

    }

  };

  return (

    <main className="forgot-page">

      <div className="login-glow login-glow-left" />

      <div className="login-glow login-glow-right" />

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

            Reset
            <br />
            Your
            <br />
            Password.

          </h1>

          <p className="login-description">

            Securely update your password and continue
            using Oncology AI with confidence.

          </p>

          <div className="login-stats">

            {stats.map(({ icon: Icon, value, label }) => (

              <article className="login-stat-card" key={label}>

                <div className="login-stat-heading">

                  <Icon className="login-stat-icon" />

                  <strong>{value}</strong>

                </div>

                <p>{label}</p>

              </article>

            ))}

          </div>

        </motion.section>
                <motion.section
          className="login-form-card"
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7 }}
        >

          <h2>Forgot Password</h2>

          <p className="login-subtitle">
            Enter your email and create a new password.
          </p>

          <form onSubmit={handleReset}>

            <div className="login-field">

              <label>Email</label>

              <div className="login-input-wrap">

                <FaEnvelope />

                <input
                  type="email"
                  placeholder="Enter Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />

              </div>

            </div>

            <div className="login-field">

              <label>New Password</label>

              <div className="login-input-wrap">

                <FaLock />

                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter New Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() =>
                    setShowPassword(!showPassword)
                  }
                >

                  {showPassword ? (
                    <FaEyeSlash />
                  ) : (
                    <FaEye />
                  )}

                </button>

              </div>

            </div>

            <div className="login-field">

              <label>Confirm Password</label>

              <div className="login-input-wrap">

                <FaLock />

                <input
                  type={
                    showConfirmPassword
                      ? "text"
                      : "password"
                  }
                  placeholder="Confirm Password"
                  value={confirmPassword}
                  onChange={(e) =>
                    setConfirmPassword(e.target.value)
                  }
                  required
                />

                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() =>
                    setShowConfirmPassword(
                      !showConfirmPassword
                    )
                  }
                >

                  {showConfirmPassword ? (
                    <FaEyeSlash />
                  ) : (
                    <FaEye />
                  )}

                </button>

              </div>

            </div>

            {error && (

              <p
                style={{
                  color: "#dc2626",
                  marginBottom: "15px",
                  fontWeight: 600,
                }}
              >
                {error}
              </p>

            )}

            {success && (

              <p
                style={{
                  color: "#059669",
                  marginBottom: "15px",
                  fontWeight: 600,
                }}
              >
                {success}
              </p>

            )}

            <button
              className="login-submit"
              type="submit"
              disabled={loading}
            >

              <span>

                {loading
                  ? "Updating..."
                  : "Reset Password"}

              </span>

              <FaArrowRight />

            </button>

          </form>

          <button
            className="login-forgot"
            onClick={() => navigate("/")}
          >

            <FaArrowLeft
              style={{ marginRight: "8px" }}
            />

            Back to Login

          </button>

          <p className="login-security">

            Secure • AI Powered • Enterprise Ready

          </p>

        </motion.section>

      </div>

    </main>

  );

}
