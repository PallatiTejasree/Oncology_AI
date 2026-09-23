import API from "./api";

/**
 * Upload one or more medical files
 */
export const uploadFiles = async (email, files, sessionId = null, onProgress = null) => {
  try {
    const formData = new FormData();

    formData.append("email", email);
    if (sessionId) formData.append("session_id", sessionId);

    files.forEach((file) => {
      formData.append("files", file);
    });

    const response = await API.post(
      "/upload",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: (event) => {
          if (!onProgress || !event.total) return;
          // Keep 100% reserved for the completed server response. The browser
          // can finish sending bytes while the backend is still processing and
          // indexing the medical files.
          onProgress(Math.min(99, Math.round((event.loaded * 100) / event.total)));
        },
      }
    );

    return response.data;

  } catch (error) {
    console.error("Upload Error:", error);

    throw error;
  }
};

/**
 * Get all upload sessions for a user
 */
export const getUploadHistory = async (email) => {
  try {
    const response = await API.get(
      `/upload/history/${email}`
    );

    return response.data;

  } catch (error) {
    console.error("History Error:", error);

    throw error;
  }
};

/**
 * Get details of a single upload session
 */
export const getUploadSession = async (sessionId) => {
  try {
    const response = await API.get(
      `/upload/session/${sessionId}`
    );

    return response.data;

  } catch (error) {
    console.error("Session Error:", error);

    throw error;
  }
};

/**
 * Delete an upload session
 */
export const deleteUploadSession = async (sessionId) => {
  try {
    const response = await API.delete(
      `/upload/session/${sessionId}`
    );

    return response.data;

  } catch (error) {
    console.error("Delete Error:", error);

    throw error;
  }
};

export const archiveUploadSession = async (sessionId) => {
  const response = await API.patch(`/upload/session/${sessionId}/archive`);
  return response.data;
};

export const restoreUploadSession = async (sessionId) => {
  const response = await API.patch(`/upload/session/${sessionId}/restore`);
  return response.data;
};

export const renameUploadSession = async (sessionId, name) => {
  const response = await API.patch(`/upload/session/${sessionId}/name`, { name });
  return response.data;
};

export const getArchivedSessions = async () => {
  const response = await API.get("/upload/archive");
  return response.data;
};

export const getRejectedUploads = async () => {
  const response = await API.get("/upload/rejected");
  return response.data;
};

export const recheckRejectedUploads = async (sessionId) => {
  const response = await API.post(`/upload/session/${sessionId}/recheck-rejected`);
  return response.data;
};
