import API from "./api";

/*
-----------------------------------
Get User Profile
GET /profile/{email}
-----------------------------------
*/
export const getProfile = async (email) => {
  try {
    const response = await API.get(`/profile/${email}`);
    return response.data;
  } catch (error) {
    console.error("Get Profile Error:", error);
    throw error;
  }
};

/*
-----------------------------------
Update User Profile
PUT /profile/{email}
-----------------------------------
*/
export const updateProfile = async (
  email,
  profileData
) => {
  try {
    const response = await API.put(
      `/profile/${email}`,
      profileData
    );

    return response.data;
  } catch (error) {
    console.error("Update Profile Error:", error);
    throw error;
  }
};