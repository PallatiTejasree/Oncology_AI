import React, { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import api from "../../services/api";

export default function ProtectedRoute() {
  const location = useLocation();
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("access_token");

    if (!token) {
      setStatus("unauthenticated");
      return () => { active = false; };
    }

    api.get("/auth/me")
      .then(({ data }) => {
        if (!active) return;
        localStorage.setItem("email", data.email);
        localStorage.setItem("user", JSON.stringify(data));
        setStatus("authenticated");
      })
      .catch(() => {
        if (active) setStatus("unauthenticated");
      });

    return () => { active = false; };
  }, []);

  if (status === "checking") {
    return <main className="route-checking" role="status">Verifying secure session…</main>;
  }
  if (status === "unauthenticated") {
    return <Navigate to="/" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
