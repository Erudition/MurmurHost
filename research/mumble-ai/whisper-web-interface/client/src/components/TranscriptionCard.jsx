import React, { useState } from 'react';
import { 
  File, 
  Clock, 
  Globe, 
  Trash2, 
  Copy, 
  Check, 
  ChevronDown, 
  ChevronUp,
  Download,
  Users
} from 'lucide-react';
import { formatFileSize, formatDuration, formatDate, formatLanguage, formatText, formatSegmentText, getSpeakerCount } from '../utils/formatters';
import { deleteTranscription } from '../services/api';
import SummaryPanel from './SummaryPanel';
import TimelineView from './TimelineView';
import SpeakerEditor from './SpeakerEditor';
import SpeakerManager from './SpeakerManager';

const TranscriptionCard = ({ transcription, onDelete, onUpdate }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [viewMode, setViewMode] = useState('inline');
  const [currentSegments, setCurrentSegments] = useState(transcription.transcription_segments);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(transcription.transcription_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy text:', error);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this transcription?')) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteTranscription(transcription.id);
      onDelete(transcription.id);
    } catch (error) {
      console.error('Error deleting transcription:', error);
      alert('Failed to delete transcription. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSummaryUpdate = (updatedTranscription) => {
    onUpdate(updatedTranscription);
  };

  const handleSpeakerUpdate = (updatedData) => {
    // Update local state
    setCurrentSegments(updatedData.transcription_segments);

    // Update parent component
    onUpdate({
      ...transcription,
      transcription_segments: updatedData.transcription_segments,
      transcription_formatted: updatedData.transcription_formatted
    });
  };

  const handleSpeakersSaved = () => {
    // Trigger a refresh by notifying parent
    // Parent should re-fetch transcription to get updated speaker labels
    if (onUpdate) {
      // Force a reload of the transcription from parent
      window.location.reload(); // Simple approach for now
    }
  };

  return (
    <div className="card hover:shadow-lg transition-shadow duration-200">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-2">
            <File className="w-5 h-5 text-gray-500 flex-shrink-0" />
            <h3 className="font-medium text-gray-900 truncate">
              {transcription.filename}
            </h3>
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
              {transcription.original_format ? transcription.original_format.toUpperCase() : 'UNKNOWN'}
            </span>
          </div>
          
          <div className="flex items-center space-x-4 text-sm text-gray-500 mb-3">
            <div className="flex items-center space-x-1">
              <Clock className="w-4 h-4" />
              <span>{formatDuration(transcription.duration_seconds)}</span>
            </div>
            <div className="flex items-center space-x-1">
              <Globe className="w-4 h-4" />
              <span>{formatLanguage(transcription.language, transcription.language_probability)}</span>
            </div>
            {transcription.transcription_segments && getSpeakerCount(transcription.transcription_segments) > 1 && (
              <div className="flex items-center space-x-1">
                <Users className="w-4 h-4" />
                <span>{getSpeakerCount(transcription.transcription_segments)} speakers</span>
              </div>
            )}
            <span>{formatFileSize(transcription.file_size_bytes)}</span>
            <span>{formatDate(transcription.created_at)}</span>
          </div>
          
          {transcription.processing_time_seconds && (
            <div className="text-xs text-gray-400 mb-3">
              Processed in {transcription.processing_time_seconds.toFixed(1)}s
            </div>
          )}
        </div>
        
        <div className="flex items-center space-x-2 ml-4">
          <button
            onClick={handleCopy}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            title="Copy transcription"
          >
            {copied ? (
              <Check className="w-4 h-4 text-green-600" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
          </button>
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
          
          <button
            onClick={handleDelete}
            className="p-2 text-gray-400 hover:text-red-600 transition-colors"
            title="Delete transcription"
            disabled={isDeleting}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-2">
                <h4 className="font-medium text-gray-700">Transcription</h4>
                {transcription.transcription_segments && transcription.transcription_segments.length > 0 && (
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setViewMode('inline')}
                      className={`px-3 py-1 text-sm rounded transition-colors ${
                        viewMode === 'inline'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Inline
                    </button>
                    <button
                      onClick={() => setViewMode('timeline')}
                      className={`px-3 py-1 text-sm rounded transition-colors ${
                        viewMode === 'timeline'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Timeline
                    </button>
                  </div>
                )}
              </div>
              
              {currentSegments && currentSegments.length > 0 ? (
                viewMode === 'inline' ? (
                  <div className="bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto border border-gray-200">
                    <div className="prose prose-sm max-w-none">
                      <div className="text-gray-800 leading-relaxed whitespace-pre-wrap space-y-4">
                        {formatSegmentText(currentSegments)}
                      </div>
                    </div>
                  </div>
                ) : (
                  <TimelineView 
                    transcriptionId={transcription.id}
                    segments={currentSegments} 
                    onUpdate={handleSpeakerUpdate}
                  />
                )
              ) : (
                <div className="bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto border border-gray-200">
                  <div className="prose prose-sm max-w-none">
                    <div className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                      {formatText(transcription.transcription_text)}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {currentSegments && currentSegments.length > 0 && getSpeakerCount(currentSegments) > 0 && (
              <>
                <SpeakerManager
                  transcriptionId={transcription.id}
                  segments={currentSegments}
                  speakerMatches={transcription.speaker_matches}
                  onSpeakersSaved={handleSpeakersSaved}
                />

                <SpeakerEditor
                  transcriptionId={transcription.id}
                  segments={currentSegments}
                  onUpdate={handleSpeakerUpdate}
                />
              </>
            )}

            <SummaryPanel
              transcriptionId={transcription.id}
              transcriptionText={transcription.transcription_text}
              summaryText={transcription.summary_text}
              summaryModel={transcription.summary_model}
              onUpdate={handleSummaryUpdate}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default TranscriptionCard;
