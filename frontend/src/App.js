import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login/Login";
import Dashboard from "./pages/Dashboard/Dashboard";
import ForgotPassword from "./pages/ForgotPassword/ForgotPassword";
import CompleteProfile from "./pages/CompleteProfile/CompleteProfile";
import Profile from "./pages/Profile/Profile";
import Settings from "./pages/Settings/Settings";
import Results from "./pages/Results/Results";
import History from "./pages/History/History";
import Archive from "./pages/Archive/Archive";
import Register from "./pages/Register/Register";
import ProtectedRoute from "./components/ProtectedRoute/ProtectedRoute";

function App() {
  return (
    <Routes>
      {/* Default Route */}
      <Route path="/" element={<Login />} />

      {/* Register */}
      <Route path="/register" element={<Register />} />

      {/* Forgot Password */}
      <Route
        path="/forgot-password"
        element={<ForgotPassword />}
      />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/complete-profile" element={<CompleteProfile />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/processing" element={<Navigate to="/dashboard" replace />} />
        <Route path="/results" element={<Results />} />
        <Route path="/history" element={<History />} />
        <Route path="/archive" element={<Archive />} />
      </Route>

      {/* Redirect genuinely unknown URLs only after all application routes. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
