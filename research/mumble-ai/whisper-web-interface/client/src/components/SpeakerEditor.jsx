import React, { useState, useEffect } from 'react';
import { Users, Edit2, Save, X, Merge, ArrowRight } from 'lucide-react';
import { updateSpeakers } from '../services/api';

const SpeakerEditor = ({ transcriptionId, segments, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [speakerMappings, setSpeakerMappings] = useState({});
  const [uniqueSpeakers, setUniqueSpeakers] = useState([]);
  const [isMerging, setIsMerging] = useState(false);
  const [selectedSpeakers, setSelectedSpeakers] = useState([]);
  const [targetSpeaker, setTargetSpeaker] = useState('');

  useEffect(() => {
    if (segments && segments.length > 0) {
      // Extract unique speakers from segments
      const speakers = [...new Set(segments.map(seg => seg.speaker).filter(Boolean))].sort();
      setUniqueSpeakers(speakers);

      // Initialize mappings with current speaker names
      const initialMappings = {};
      speakers.forEach(speaker => {
        initialMappings[speaker] = speaker;
      });
      setSpeakerMappings(initialMappings);
    }
  }, [segments]);

  const handleSpeakerNameChange = (oldName, newName) => {
    setSpeakerMappings({
      ...speakerMappings,
      [oldName]: newName
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Only send mappings that have actually changed
      const changedMappings = {};
      Object.entries(speakerMappings).forEach(([oldName, newName]) => {
        if (oldName !== newName && newName.trim() !== '') {
          changedMappings[oldName] = newName.trim();
        }
      });

      if (Object.keys(changedMappings).length === 0) {
        setIsEditing(false);
        setIsSaving(false);
        return;
      }

      const response = await updateSpeakers(transcriptionId, changedMappings);

      // Update the parent component with the new data
      if (onUpdate && response.success) {
        onUpdate({
          transcription_segments: response.transcription_segments,
          transcription_formatted: response.transcription_formatted
        });
      }

      setIsEditing(false);
    } catch (error) {
      console.error('Error updating speakers:', error);
      alert('Failed to update speaker names. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    // Reset mappings to original names
    const resetMappings = {};
    uniqueSpeakers.forEach(speaker => {
      resetMappings[speaker] = speaker;
    });
    setSpeakerMappings(resetMappings);
    setIsEditing(false);
    setIsMerging(false);
    setSelectedSpeakers([]);
    setTargetSpeaker('');
  };

  const handleSpeakerSelection = (speaker) => {
    setSelectedSpeakers(prev => 
      prev.includes(speaker) 
        ? prev.filter(s => s !== speaker)
        : [...prev, speaker]
    );
  };

  const handleMerge = async () => {
    if (selectedSpeakers.length < 2 || !targetSpeaker) {
      alert('Please select at least 2 speakers to merge and choose a target speaker.');
      return;
    }

    setIsSaving(true);
    try {
      // Create merge mappings
      const mergeMappings = {};
      selectedSpeakers.forEach(speaker => {
        mergeMappings[speaker] = targetSpeaker;
      });

      const response = await updateSpeakers(transcriptionId, mergeMappings);

      if (onUpdate && response.success) {
        onUpdate({
          transcription_segments: response.transcription_segments,
          transcription_formatted: response.transcription_formatted
        });
      }

      setIsMerging(false);
      setSelectedSpeakers([]);
      setTargetSpeaker('');
    } catch (error) {
      console.error('Error merging speakers:', error);
      alert('Failed to merge speakers. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!segments || segments.length === 0 || uniqueSpeakers.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Users className="w-5 h-5 text-gray-600" />
          <h4 className="font-medium text-gray-700">
            Speaker Labels ({uniqueSpeakers.length} {uniqueSpeakers.length === 1 ? 'speaker' : 'speakers'})
          </h4>
        </div>
        {!isEditing && !isMerging ? (
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              <Edit2 className="w-3 h-3" />
              <span>Edit Names</span>
            </button>
            {uniqueSpeakers.length > 1 && (
              <button
                onClick={() => setIsMerging(true)}
                className="flex items-center space-x-1 px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
              >
                <Merge className="w-3 h-3" />
                <span>Merge Speakers</span>
              </button>
            )}
          </div>
        ) : isEditing ? (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              <Save className="w-3 h-3" />
              <span>{isSaving ? 'Saving...' : 'Save'}</span>
            </button>
            <button
              onClick={handleCancel}
              disabled={isSaving}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition-colors disabled:opacity-50"
            >
              <X className="w-3 h-3" />
              <span>Cancel</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleMerge}
              disabled={isSaving || selectedSpeakers.length < 2 || !targetSpeaker}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              <Merge className="w-3 h-3" />
              <span>{isSaving ? 'Merging...' : 'Apply Merge'}</span>
            </button>
            <button
              onClick={handleCancel}
              disabled={isSaving}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition-colors disabled:opacity-50"
            >
              <X className="w-3 h-3" />
              <span>Cancel</span>
            </button>
          </div>
        )}
      </div>

      {isMerging ? (
        <div className="space-y-4">
          <div>
            <h5 className="font-medium text-gray-700 mb-2">Select speakers to merge:</h5>
            <div className="space-y-2">
              {uniqueSpeakers.map((speaker) => (
                <label key={speaker} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={selectedSpeakers.includes(speaker)}
                    onChange={() => handleSpeakerSelection(speaker)}
                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  />
                  <span className="text-sm text-gray-700">{speaker}</span>
                </label>
              ))}
            </div>
          </div>
          
          <div>
            <h5 className="font-medium text-gray-700 mb-2">Merge into:</h5>
            <select
              value={targetSpeaker}
              onChange={(e) => setTargetSpeaker(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">Select target speaker...</option>
              {uniqueSpeakers.filter(s => !selectedSpeakers.includes(s)).map((speaker) => (
                <option key={speaker} value={speaker}>{speaker}</option>
              ))}
            </select>
          </div>

          {selectedSpeakers.length >= 2 && targetSpeaker && (
            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <div className="flex items-center space-x-2 text-blue-800">
                <ArrowRight className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {selectedSpeakers.length} speakers will be merged into {targetSpeaker}
                </span>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {uniqueSpeakers.map((speaker) => (
            <div key={speaker} className="flex items-center space-x-3">
              <div className="w-32 text-sm text-gray-600 font-medium">
                {speaker}
              </div>
              <div className="flex-1">
                {isEditing ? (
                  <input
                    type="text"
                    value={speakerMappings[speaker] || speaker}
                    onChange={(e) => handleSpeakerNameChange(speaker, e.target.value)}
                    className="w-full px-3 py-1 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    placeholder="Enter speaker name..."
                  />
                ) : (
                  <div className="px-3 py-1 bg-gray-50 rounded text-sm text-gray-700">
                    {speakerMappings[speaker] || speaker}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {isEditing && (
        <div className="mt-3 text-xs text-gray-500">
          Enter custom names for each speaker. Leave blank to keep the original label.
        </div>
      )}
    </div>
  );
};

export default SpeakerEditor;