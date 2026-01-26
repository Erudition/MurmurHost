import React, { useState } from 'react';
import { Copy, Check, Save, X } from 'lucide-react';
import { formatTimestamp, getSpeakerColor } from '../utils/formatters';
import { updateSegmentSpeakers } from '../services/api';

const TimelineView = ({ transcriptionId, segments, onUpdate }) => {
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [segmentChanges, setSegmentChanges] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  const handleCopySegment = async (index, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleSpeakerChange = (index, newSpeaker) => {
    setSegmentChanges(prev => ({
      ...prev,
      [index]: newSpeaker
    }));
  };

  const handleSaveChanges = async () => {
    if (Object.keys(segmentChanges).length === 0) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      const response = await updateSegmentSpeakers(transcriptionId, segmentChanges);
      
      if (onUpdate && response.success) {
        onUpdate({
          transcription_segments: response.transcription_segments,
          transcription_formatted: response.transcription_formatted
        });
      }

      setSegmentChanges({});
      setIsEditing(false);
    } catch (error) {
      console.error('Error updating segment speakers:', error);
      alert('Failed to update segment speakers. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setSegmentChanges({});
    setIsEditing(false);
  };

  const getUniqueSpeakers = () => {
    const speakers = new Set(segments.map(seg => seg.speaker).filter(Boolean));
    return Array.from(speakers).sort();
  };

  if (!segments || segments.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 text-gray-500 text-center">
        No segment data available
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
        <h4 className="font-semibold text-gray-800">Timeline View</h4>
        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            className="flex items-center space-x-1 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            <span>Edit Speakers</span>
          </button>
        ) : (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSaveChanges}
              disabled={isSaving || Object.keys(segmentChanges).length === 0}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              <Save className="w-3 h-3" />
              <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
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
      
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-100 sticky top-0 z-10">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Time
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Speaker
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Text
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {segments.map((segment, index) => {
              const currentSpeaker = segmentChanges[index] !== undefined ? segmentChanges[index] : segment.speaker;
              const isModified = segmentChanges[index] !== undefined;
              
              return (
                <tr key={index} className={`hover:bg-blue-50 transition-colors ${isModified ? 'bg-yellow-50' : ''}`}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-600 font-medium">
                    {formatTimestamp(segment.start)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {isEditing ? (
                      <select
                        value={currentSpeaker || 'Speaker 1'}
                        onChange={(e) => handleSpeakerChange(index, e.target.value)}
                        className="text-xs border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {getUniqueSpeakers().map(speaker => (
                          <option key={speaker} value={speaker}>{speaker}</option>
                        ))}
                      </select>
                    ) : (
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${getSpeakerColor(currentSpeaker)}`}>
                        {currentSpeaker || 'Speaker 1'}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-800 leading-relaxed">
                    {segment.text}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleCopySegment(index, segment.text)}
                      className="text-gray-400 hover:text-blue-600 transition-colors p-1 rounded hover:bg-blue-50"
                      title="Copy segment"
                    >
                      {copiedIndex === index ? (
                        <Check className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TimelineView;

