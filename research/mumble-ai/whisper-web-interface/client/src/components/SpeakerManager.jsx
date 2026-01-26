import React, { useState, useEffect } from 'react';
import { Users, Save, X, Check, AlertCircle } from 'lucide-react';
import { getSpeakers, createSpeakerProfile } from '../services/api';
import { getSpeakerColor } from '../utils/formatters';

const SpeakerManager = ({ transcriptionId, segments, speakerMatches, onSpeakersSaved }) => {
  const [speakers, setSpeakers] = useState([]);
  const [loadingSpeakers, setLoadingSpeakers] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [speakerNames, setSpeakerNames] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Extract unique detected speakers from segments
  const detectedSpeakers = React.useMemo(() => {
    if (!segments) return [];
    const unique = new Set();
    segments.forEach(seg => {
      const speaker = seg.speaker || 'Speaker 1';
      // Only add if it's a generic "Speaker N" label (not already named)
      if (speaker.match(/^Speaker \d+$/)) {
        unique.add(speaker);
      }
    });
    return Array.from(unique).sort();
  }, [segments]);

  useEffect(() => {
    loadSpeakers();
  }, []);

  const loadSpeakers = async () => {
    try {
      setLoadingSpeakers(true);
      const data = await getSpeakers();
      setSpeakers(data.speakers || []);
    } catch (err) {
      console.error('Failed to load speakers:', err);
    } finally {
      setLoadingSpeakers(false);
    }
  };

  const handleSaveSpeakers = async () => {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const updates = [];

      // Save each named speaker
      for (const [detectedLabel, name] of Object.entries(speakerNames)) {
        if (name && name.trim()) {
          await createSpeakerProfile(
            name.trim(),
            transcriptionId,
            detectedLabel
          );
          updates.push({ label: detectedLabel, name: name.trim() });
        }
      }

      if (updates.length > 0) {
        setSuccessMessage(`Successfully saved ${updates.length} speaker profile(s)`);
        setSpeakerNames({});
        setIsEditing(false);

        // Reload speakers list
        await loadSpeakers();

        // Notify parent to refresh transcription
        if (onSpeakersSaved) {
          onSpeakersSaved();
        }

        // Clear success message after 3 seconds
        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        setError('No speaker names provided');
      }
    } catch (err) {
      console.error('Failed to save speakers:', err);
      setError('Failed to save speaker profiles. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleNameChange = (detectedLabel, value) => {
    setSpeakerNames(prev => ({
      ...prev,
      [detectedLabel]: value
    }));
  };

  const getSpeakerMatchInfo = (detectedLabel) => {
    if (speakerMatches && speakerMatches[detectedLabel]) {
      return speakerMatches[detectedLabel];
    }
    return null;
  };

  if (detectedSpeakers.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-2">
          <Users className="w-5 h-5 text-gray-600" />
          <h4 className="font-semibold text-gray-800">Speaker Recognition</h4>
        </div>
        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            className="flex items-center space-x-1 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            <span>Name Speakers</span>
          </button>
        ) : (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSaveSpeakers}
              disabled={saving || Object.keys(speakerNames).length === 0}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="w-3 h-3" />
              <span>{saving ? 'Saving...' : 'Save Profiles'}</span>
            </button>
            <button
              onClick={() => {
                setIsEditing(false);
                setSpeakerNames({});
                setError(null);
              }}
              disabled={saving}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition-colors disabled:opacity-50"
            >
              <X className="w-3 h-3" />
              <span>Cancel</span>
            </button>
          </div>
        )}
      </div>

      <div className="p-4">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start space-x-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-start space-x-2">
            <Check className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <span className="text-sm text-green-700">{successMessage}</span>
          </div>
        )}

        <div className="space-y-3">
          {detectedSpeakers.map(detectedLabel => {
            const matchInfo = getSpeakerMatchInfo(detectedLabel);
            const isMatched = matchInfo && matchInfo.matched;

            return (
              <div
                key={detectedLabel}
                className={`p-3 rounded-lg border ${
                  isMatched ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3 flex-1">
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${getSpeakerColor(detectedLabel)}`}>
                      {detectedLabel}
                    </span>

                    {isMatched ? (
                      <div className="flex items-center space-x-2">
                        <Check className="w-4 h-4 text-green-600" />
                        <span className="text-sm font-medium text-green-700">
                          Matched: {matchInfo.profile_name}
                        </span>
                        <span className="text-xs text-green-600">
                          ({(matchInfo.similarity * 100).toFixed(1)}% confidence)
                        </span>
                      </div>
                    ) : isEditing ? (
                      <div className="flex-1 max-w-md">
                        <input
                          type="text"
                          placeholder="Enter speaker name (e.g., John Doe)"
                          value={speakerNames[detectedLabel] || ''}
                          onChange={(e) => handleNameChange(detectedLabel, e.target.value)}
                          className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    ) : (
                      <span className="text-sm text-gray-500">
                        Unknown speaker (click "Name Speakers" to identify)
                      </span>
                    )}
                  </div>
                </div>

                {matchInfo && !matchInfo.matched && (
                  <div className="mt-2 text-xs text-gray-500">
                    Best match: {matchInfo.similarity > 0 ? `${(matchInfo.similarity * 100).toFixed(1)}% similar to stored voices` : 'No similar voices found'}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {!isEditing && detectedSpeakers.some(label => !getSpeakerMatchInfo(label)?.matched) && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-700">
              💡 Name these speakers to enable automatic recognition in future transcriptions
            </p>
          </div>
        )}

        {loadingSpeakers ? (
          <div className="mt-4 text-sm text-gray-500">Loading speaker profiles...</div>
        ) : speakers.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h5 className="text-sm font-semibold text-gray-700 mb-2">Known Speakers ({speakers.filter(s => s.is_active).length})</h5>
            <div className="flex flex-wrap gap-2">
              {speakers
                .filter(s => s.is_active)
                .slice(0, 10)
                .map(speaker => (
                  <span
                    key={speaker.id}
                    className="inline-flex items-center px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
                    title={`${speaker.sample_count} samples, ${speaker.total_duration_seconds.toFixed(1)}s total`}
                  >
                    {speaker.speaker_name}
                  </span>
                ))}
              {speakers.filter(s => s.is_active).length > 10 && (
                <span className="inline-flex items-center px-2 py-1 text-gray-500 text-xs">
                  +{speakers.filter(s => s.is_active).length - 10} more
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SpeakerManager;
