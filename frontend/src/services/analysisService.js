import API from "./api";

export const analyzeSession = async (sessionId, question = "", topK = 5) => {
  const response = await API.post(`/analysis/session/${sessionId}`, {
    question: question || null,
    top_k: topK,
  });
  return response.data;
};

export const analyzeText = async (text, topK = 5) => {
  const response = await API.post("/analysis/text", { text, top_k: topK });
  return response.data;
};

export const clearConversationCache = async (sessionId) => {
  const response = await API.delete(`/analysis/session/${sessionId}/cache`);
  return response.data;
};
