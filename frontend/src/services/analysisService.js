import API from "./api";

const ANALYSIS_TIMEOUT_MS = 70000;

const runAnalysisRequest = async (request) => {
  try {
    return await request();
  } catch (error) {
    if (error.code === "ECONNABORTED") {
      throw new Error("Analysis timed out. The clinical AI service did not respond in time; please try again.");
    }
    throw error;
  }
};

export const analyzeSession = async (sessionId, question = "", topK = 5, signal) => {
  const response = await runAnalysisRequest(() => API.post(`/analysis/session/${sessionId}`, {
    question: question || null,
    top_k: topK,
  }, { timeout: ANALYSIS_TIMEOUT_MS, signal }));
  return response.data;
};

export const analyzeText = async (text, topK = 5, signal) => {
  const response = await runAnalysisRequest(() => API.post("/analysis/text", { text, top_k: topK }, {
    timeout: ANALYSIS_TIMEOUT_MS,
    signal,
  }));
  return response.data;
};

export const clearConversationCache = async (sessionId) => {
  const response = await API.delete(`/analysis/session/${sessionId}/cache`);
  return response.data;
};
