import api from "./api";

export const loginUser = async (email, password) => {
  const response = await api.post("/auth/login", {
    email,
    password,
  });

  return response.data;
};

export const registerUser = async (email, password, recoveryPin) => {
  const response = await api.post("/auth/register", {
    email,
    password,
    recovery_pin: recoveryPin,
  });

  return response.data;
};

export const forgotPassword = async (email, newPassword) => {
  const response = await api.post("/auth/forgot-password", {
    email,
    new_password: newPassword,
  });

  return response.data;
};
