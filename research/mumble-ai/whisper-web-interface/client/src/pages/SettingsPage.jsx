import React, { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, CheckCircle, AlertCircle, Loader2, ChevronDown } from 'lucide-react';
import { getSettings, updateSettings, testOllamaConnection, getOllamaModels } from '../services/api';

function SettingsPage() {
  const [settings, setSettings] = useState({
    ollama_url: '',
    ollama_model: '',
    whisper_url: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saveMessage, setSaveMessage] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [modelFetchError, setModelFetchError] = useState(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await getSettings();
      if (data.success) {
        setSettings(data.settings);
      }
    } catch (error) {
      console.error('Error loading settings:', error);
      alert('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaveMessage(null);
      const result = await updateSettings({
        ollama_url: settings.ollama_url,
        ollama_model: settings.ollama_model
      });

      if (result.success) {
        setSaveMessage({ type: 'success', text: 'Settings saved successfully!' });
        setTimeout(() => setSaveMessage(null), 3000);
      } else {
        setSaveMessage({ type: 'error', text: 'Failed to save settings' });
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      setSaveMessage({ type: 'error', text: `Error: ${error.message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      setTesting(true);
      setTestResult(null);
      const result = await testOllamaConnection(settings.ollama_url, settings.ollama_model);
      setTestResult(result);
    } catch (error) {
      console.error('Error testing connection:', error);
      setTestResult({
        success: false,
        error: 'Connection test failed: ' + error.message
      });
    } finally {
      setTesting(false);
    }
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
    setTestResult(null);
    setSaveMessage(null);
  };

  const handleFetchModels = async () => {
    if (!settings.ollama_url) {
      setModelFetchError('Please enter an Ollama URL first');
      return;
    }

    try {
      setFetchingModels(true);
      setModelFetchError(null);
      const result = await getOllamaModels(settings.ollama_url);

      if (result.success && result.models) {
        setAvailableModels(result.models);
        if (result.models.length === 0) {
          setModelFetchError('No models found on server');
        }
      } else {
        setModelFetchError('Failed to fetch models from server');
      }
    } catch (error) {
      console.error('Error fetching models:', error);
      setModelFetchError(`Error: ${error.message || 'Failed to connect to Ollama server'}`);
    } finally {
      setFetchingModels(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex items-center">
          <Loader2 className="w-6 h-6 animate-spin text-purple-600 mr-3" />
          <span>Loading settings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <div className="flex items-center mb-2">
            <Settings className="w-8 h-8 text-purple-600 mr-3" />
            <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          </div>
          <p className="text-gray-600">Configure Ollama server and AI model settings</p>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          {/* Ollama URL */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Ollama Server URL
            </label>
            <input
              type="text"
              value={settings.ollama_url}
              onChange={(e) => handleChange('ollama_url', e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="http://host.docker.internal:11434"
            />
            <p className="mt-1 text-sm text-gray-500">
              The URL of your Ollama server (e.g., http://localhost:11434)
            </p>
          </div>

          {/* Ollama Model */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Ollama Model
              </label>
              <button
                onClick={handleFetchModels}
                disabled={fetchingModels || !settings.ollama_url}
                className="flex items-center gap-1 px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                {fetchingModels ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Fetching...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3 h-3" />
                    Fetch Models
                  </>
                )}
              </button>
            </div>

            {availableModels.length > 0 ? (
              <div className="relative">
                <select
                  value={settings.ollama_model}
                  onChange={(e) => handleChange('ollama_model', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent appearance-none bg-white"
                >
                  <option value="">Select a model...</option>
                  {availableModels.map((model) => (
                    <option key={model.name} value={model.name}>
                      {model.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
              </div>
            ) : (
              <input
                type="text"
                value={settings.ollama_model}
                onChange={(e) => handleChange('ollama_model', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                placeholder="llama3.2:latest"
              />
            )}

            {modelFetchError && (
              <div className="mt-2 flex items-center text-sm text-red-600">
                <AlertCircle className="w-4 h-4 mr-1" />
                {modelFetchError}
              </div>
            )}

            <p className="mt-1 text-sm text-gray-500">
              {availableModels.length > 0
                ? 'Select a model from your Ollama server or type a custom model name'
                : 'Click "Fetch Models" to load available models, or type a model name manually'}
            </p>
          </div>

          {/* Whisper URL (Read-only) */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Whisper Service URL (Read-only)
            </label>
            <input
              type="text"
              value={settings.whisper_url}
              readOnly
              className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600 cursor-not-allowed"
            />
            <p className="mt-1 text-sm text-gray-500">
              The Whisper service URL is configured via environment variables
            </p>
          </div>

          {/* Test Connection Button */}
          <div className="mb-6">
            <button
              onClick={handleTestConnection}
              disabled={testing || !settings.ollama_url || !settings.ollama_model}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {testing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Testing Connection...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  Test Connection
                </>
              )}
            </button>
          </div>

          {/* Test Result */}
          {testResult && (
            <div className={`mb-6 p-4 rounded-lg ${
              testResult.success && testResult.connected
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <div className="flex items-start">
                {testResult.success && testResult.connected ? (
                  <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 mr-3 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" />
                )}
                <div className="flex-1">
                  {testResult.success && testResult.connected ? (
                    <>
                      <p className="font-medium text-green-900">Connection Successful!</p>
                      <p className="text-sm text-green-700 mt-1">
                        Server is accessible. Model {testResult.model_exists ? 'found' : 'NOT found'}.
                      </p>
                      {testResult.available_models && testResult.available_models.length > 0 && (
                        <div className="mt-2">
                          <p className="text-sm text-green-700 font-medium">Available models:</p>
                          <ul className="text-xs text-green-600 mt-1 list-disc list-inside">
                            {testResult.available_models.map((model, idx) => (
                              <li key={idx}>{model}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <p className="font-medium text-red-900">Connection Failed</p>
                      <p className="text-sm text-red-700 mt-1">{testResult.error}</p>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Save Message */}
          {saveMessage && (
            <div className={`mb-6 p-4 rounded-lg ${
              saveMessage.type === 'success'
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <div className="flex items-center">
                {saveMessage.type === 'success' ? (
                  <CheckCircle className="w-5 h-5 text-green-600 mr-3" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-red-600 mr-3" />
                )}
                <p className={saveMessage.type === 'success' ? 'text-green-900' : 'text-red-900'}>
                  {saveMessage.text}
                </p>
              </div>
            </div>
          )}

          {/* Save Button */}
          <div className="flex items-center justify-between">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {saving ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Settings
                </>
              )}
            </button>
            <button
              onClick={loadSettings}
              className="px-4 py-2 text-gray-700 hover:text-gray-900 underline"
            >
              Reset to Current
            </button>
          </div>
        </div>

        {/* Info Section */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900 mb-2">Important Notes:</h3>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>Changes take effect immediately for new AI generation requests</li>
            <li>Make sure your Ollama server is accessible from the Docker container</li>
            <li>Use <code className="bg-blue-100 px-1 rounded">host.docker.internal</code> to access the host machine from Docker</li>
            <li>The model must be already pulled in your Ollama installation</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
