import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 1800000, // 30 minutes for transcription (large files with large model)
});

// Request interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const transcribeFile = async (fileData) => {
  const response = await api.post('/transcribe', fileData);
  return response.data;
};

export const summarizeTranscription = async (transcriptionId, transcriptionText) => {
  const response = await api.post('/summarize', {
    transcription_id: transcriptionId,
    transcription_text: transcriptionText,
  });
  return response.data;
};

export const regenerateTitle = async (transcriptionId, transcriptionText) => {
  const response = await api.post('/regenerate-title', {
    transcription_id: transcriptionId,
    transcription_text: transcriptionText,
  });
  return response.data;
};

export const generateAIContent = async (transcriptionText, generationType, transcriptionId = null) => {
  const response = await api.post('/generate-ai-content', {
    transcription_text: transcriptionText,
    generation_type: generationType,
    transcription_id: transcriptionId,
  });
  return response.data;
};

export const getAIContent = async (transcriptionId) => {
  const response = await api.get(`/get-ai-content/${transcriptionId}`);
  return response.data;
};

export const getTranscriptions = async (page = 1, perPage = 10, search = '') => {
  const response = await api.get('/transcriptions', {
    params: { page, per_page: perPage, search },
  });
  return response.data;
};

export const getTranscription = async (id) => {
  const response = await api.get(`/transcriptions/${id}`);
  return response.data;
};

export const deleteTranscription = async (id) => {
  const response = await api.delete(`/transcriptions/${id}`);
  return response.data;
};

export const updateSpeakers = async (id, speakerMappings) => {
  const response = await api.post(`/transcriptions/${id}/update-speakers`, {
    speaker_mappings: speakerMappings,
  });
  return response.data;
};

export const updateSegmentSpeakers = async (id, segmentUpdates) => {
  const response = await api.post(`/transcriptions/${id}/update-segment-speakers`, {
    segment_updates: segmentUpdates,
  });
  return response.data;
};

// Speaker profile management
export const getSpeakers = async () => {
  const response = await api.get('/speakers');
  return response.data;
};

export const createSpeakerProfile = async (speakerName, transcriptionId, detectedSpeakerLabel, description = '', tags = []) => {
  const response = await api.post('/speakers', {
    speaker_name: speakerName,
    transcription_id: transcriptionId,
    detected_speaker_label: detectedSpeakerLabel,
    description,
    tags,
  });
  return response.data;
};

export const updateSpeakerProfile = async (profileId, data) => {
  const response = await api.put(`/speakers/${profileId}`, data);
  return response.data;
};

export const deleteSpeakerProfile = async (profileId) => {
  const response = await api.delete(`/speakers/${profileId}`);
  return response.data;
};

// Settings management
export const getSettings = async () => {
  const response = await api.get('/settings');
  return response.data;
};

export const updateSettings = async (settings) => {
  const response = await api.post('/settings', settings);
  return response.data;
};

export const testOllamaConnection = async (url, model) => {
  const response = await api.post('/settings/test-ollama', {
    url,
    model,
  });
  return response.data;
};

export const getOllamaModels = async (url) => {
  const response = await api.post('/settings/ollama-models', {
    url,
  });
  return response.data;
};

export default api;
