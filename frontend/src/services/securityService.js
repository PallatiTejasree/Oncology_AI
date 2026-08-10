import API from "./api";

export const changePassword = async (oldPassword, newPassword) => {
  const response = await API.post("/auth/change-password", {
    old_password: oldPassword,
    new_password: newPassword,
  });
  return response.data;
};
