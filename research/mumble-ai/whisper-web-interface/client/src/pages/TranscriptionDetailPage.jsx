import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Globe, Users, Trash2, FileText, Sparkles, Download } from 'lucide-react';
import { getTranscription, deleteTranscription, regenerateTitle } from '../services/api';
import { formatFileSize, formatDuration, formatDate, formatLanguage, getSpeakerCount } from '../utils/formatters';
import SummaryPanel from '../components/SummaryPanel';
import TimelineView from '../components/TimelineView';
import SpeakerManager from '../components/SpeakerManager';
import SpeakerEditor from '../components/SpeakerEditor';
import AIGenerationPanel from '../components/AIGenerationPanel';
import LoadingSpinner from '../components/LoadingSpinner';

function TranscriptionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [transcription, setTranscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('formatted');
  const [currentSegments, setCurrentSegments] = useState(null);
  const [regeneratingTitle, setRegeneratingTitle] = useState(false);

  useEffect(() => {
    loadTranscription();
  }, [id]);

  const loadTranscription = async () => {
    try {
      setLoading(true);
      const data = await getTranscription(id);
      setTranscription(data);
      setCurrentSegments(data.transcription_segments);
      setError(null);
    } catch (err) {
      console.error('Error loading transcription:', err);
      setError('Failed to load transcription');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this transcription?')) {
      return;
    }

    try {
      await deleteTranscription(id);
      navigate('/history');
    } catch (err) {
      console.error('Error deleting transcription:', err);
      alert('Failed to delete transcription');
    }
  };

  const handleUpdate = (updatedData) => {
    setTranscription(prev => ({ ...prev, ...updatedData }));
    if (updatedData.transcription_segments) {
      setCurrentSegments(updatedData.transcription_segments);
    }
  };

  const handleSpeakerUpdate = (updatedData) => {
    setCurrentSegments(updatedData.transcription_segments);
    setTranscription(prev => ({
      ...prev,
      transcription_segments: updatedData.transcription_segments,
      transcription_formatted: updatedData.transcription_formatted
    }));
  };

  const handleRegenerateTitle = async () => {
    if (!window.confirm('Generate a new AI title for this transcription? This may take up to 5 minutes.')) {
      return;
    }

    setRegeneratingTitle(true);
    try {
      const result = await regenerateTitle(id, transcription.transcription_text);
      setTranscription(prev => ({
        ...prev,
        title: result.title
      }));
      alert('Title regenerated successfully!');
    } catch (err) {
      console.error('Error regenerating title:', err);
      alert('Failed to regenerate title. Please try again.');
    } finally {
      setRegeneratingTitle(false);
    }
  };

  const handleExportTranscript = (format) => {
    const url = `/api/export-transcript/${id}/${format}`;
    window.open(url, '_blank');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingSpinner text="Loading transcription..." />
      </div>
    );
  }

  if (error || !transcription) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 text-lg mb-4">{error || 'Transcription not found'}</p>
          <button onClick={() => navigate('/history')} className="btn-primary">
            Back to History
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/history')}
            className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to History
          </button>

          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-3xl font-bold text-gray-900">
                    {transcription.title || transcription.filename}
                  </h1>
                  <button
                    onClick={handleRegenerateTitle}
                    disabled={regeneratingTitle}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    title="Generate new AI title"
                  >
                    <Sparkles className={`w-4 h-4 ${regeneratingTitle ? 'animate-spin' : ''}`} />
                    {regeneratingTitle ? 'Generating...' : 'Magic Title'}
                  </button>
                </div>
                {transcription.title && (
                  <p className="text-sm text-gray-500 mb-4">
                    <FileText className="w-4 h-4 inline mr-1" />
                    {transcription.filename}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
                  <div className="flex items-center">
                    <Clock className="w-4 h-4 mr-1" />
                    {formatDuration(transcription.duration_seconds)}
                  </div>
                  <div className="flex items-center">
                    <Globe className="w-4 h-4 mr-1" />
                    {formatLanguage(transcription.language, transcription.language_probability)}
                  </div>
                  {currentSegments && getSpeakerCount(currentSegments) > 1 && (
                    <div className="flex items-center">
                      <Users className="w-4 h-4 mr-1" />
                      {getSpeakerCount(currentSegments)} speakers
                    </div>
                  )}
                  <span>{formatFileSize(transcription.file_size_bytes)}</span>
                  <span>{formatDate(transcription.created_at)}</span>
                </div>

                {transcription.processing_time_seconds && (
                  <p className="text-xs text-gray-400 mt-2">
                    Processed in {transcription.processing_time_seconds.toFixed(1)}s
                  </p>
                )}
              </div>

              <button
                onClick={handleDelete}
                className="ml-4 p-2 text-gray-400 hover:text-red-600 transition-colors"
                title="Delete transcription"
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Transcription Content */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Transcription</h2>
              <div className="flex space-x-2">
                {/* Export Buttons */}
                <button
                  onClick={() => handleExportTranscript('docx')}
                  className="flex items-center gap-1 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                  title="Export to Word"
                >
                  <Download className="w-4 h-4" />
                  Word
                </button>
                <button
                  onClick={() => handleExportTranscript('pdf')}
                  className="flex items-center gap-1 px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
                  title="Export to PDF"
                >
                  <Download className="w-4 h-4" />
                  PDF
                </button>
                {/* View Mode Buttons */}
                {currentSegments && currentSegments.length > 0 && (
                  <>
                    <button
                      onClick={() => setViewMode('formatted')}
                      className={`px-3 py-1 text-sm rounded transition-colors ${
                        viewMode === 'formatted'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Formatted
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
                  </>
                )}
              </div>
            </div>

            {currentSegments && currentSegments.length > 0 ? (
              viewMode === 'formatted' ? (
                <div className="bg-gray-50 rounded-lg p-6 max-h-[600px] overflow-y-auto border border-gray-200">
                  <div className="prose prose-sm max-w-none">
                    <div className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                      {transcription.transcription_formatted || transcription.transcription_text}
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
              <div className="bg-gray-50 rounded-lg p-6 max-h-[600px] overflow-y-auto border border-gray-200">
                <div className="prose prose-sm max-w-none">
                  <div className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {transcription.transcription_text}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Speaker Management */}
          {currentSegments && currentSegments.length > 0 && getSpeakerCount(currentSegments) > 0 && (
            <>
              <SpeakerManager
                transcriptionId={transcription.id}
                segments={currentSegments}
                speakerMatches={transcription.speaker_matches}
                onSpeakersSaved={loadTranscription}
              />

              <SpeakerEditor
                transcriptionId={transcription.id}
                segments={currentSegments}
                onUpdate={handleSpeakerUpdate}
              />
            </>
          )}

          {/* Summary Panel */}
          <SummaryPanel
            transcriptionId={transcription.id}
            transcriptionText={transcription.transcription_text}
            summaryText={transcription.summary_text}
            summaryModel={transcription.summary_model}
            onUpdate={handleUpdate}
          />

          {/* AI Generation Panel */}
          <AIGenerationPanel
            transcriptionText={transcription.transcription_text}
            transcriptionId={transcription.id}
          />
        </div>
      </div>
    </div>
  );
}

export default TranscriptionDetailPage;
