import React, { useState } from 'react';
import { Mic, Upload as UploadIcon } from 'lucide-react';
import UploadZone from '../components/UploadZone';
import LoadingSpinner from '../components/LoadingSpinner';
import { uploadFile, transcribeFile } from '../services/api';
import { useNavigate } from 'react-router-dom';

const SUPPORTED_FORMATS = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.mp4', '.webm', '.avi', '.mov', '.mkv'];

function HomePage() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptionProgress, setTranscriptionProgress] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleFileSelect = (file) => {
    setSelectedFile(file);
    setError('');
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError('');

    try {
      const uploadResult = await uploadFile(selectedFile);
      setSelectedFile({ ...selectedFile, ...uploadResult });
    } catch (error) {
      console.error('Upload error:', error);
      setError('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleTranscribe = async () => {
    if (!selectedFile || !selectedFile.temp_path) return;

    setIsTranscribing(true);
    setError('');
    setTranscriptionProgress('Preparing audio file...');

    try {
      const duration = selectedFile.duration_seconds || 60;
      const isVideo = ['.mp4', '.webm', '.avi', '.mov', '.mkv'].includes('.' + selectedFile.original_format);

      setTimeout(() => {
        if (isVideo) {
          setTranscriptionProgress('Extracting audio from video...');
        } else {
          setTranscriptionProgress('Processing audio file...');
        }
      }, 1000);

      setTimeout(() => {
        setTranscriptionProgress(`Transcribing with AI... This may take several minutes.`);
      }, 3000);

      const transcriptionResult = await transcribeFile(selectedFile);

      // Navigate to the transcription detail page
      navigate(`/transcription/${transcriptionResult.transcription_id}`);

    } catch (error) {
      console.error('Transcription error:', error);
      setError('Transcription failed. Please try again.');
      setTranscriptionProgress('');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setError('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center space-x-3 mb-4">
            <Mic className="w-12 h-12 text-indigo-600" />
            <h1 className="text-4xl font-bold text-gray-900">
              Whisper Transcription
            </h1>
          </div>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Upload audio or video files and get accurate transcriptions using AI with automatic speaker recognition
          </p>
        </div>

        {/* Upload Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6 flex items-center">
            <UploadIcon className="w-6 h-6 mr-2 text-indigo-600" />
            Upload Audio or Video File
          </h2>

          <UploadZone
            onFileSelect={handleFileSelect}
            isUploading={isUploading}
            supportedFormats={SUPPORTED_FORMATS}
          />

          {selectedFile && (
            <div className="mt-6 space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-green-900">
                      {selectedFile.filename}
                    </h3>
                    <p className="text-sm text-green-700">
                      {selectedFile.original_format ? selectedFile.original_format.toUpperCase() : 'UNKNOWN'} •
                      {(selectedFile.file_size_bytes / (1024 * 1024)).toFixed(1)} MB
                      {selectedFile.duration_seconds &&
                        ` • ${Math.floor(selectedFile.duration_seconds / 60)}:${Math.floor(selectedFile.duration_seconds % 60).toString().padStart(2, '0')}`
                      }
                    </p>
                  </div>
                  <button
                    onClick={handleReset}
                    className="text-green-600 hover:text-green-700 text-sm font-medium"
                  >
                    Change File
                  </button>
                </div>
              </div>

              <div className="flex space-x-3">
                {!selectedFile.temp_path && (
                  <button
                    onClick={handleUpload}
                    disabled={isUploading}
                    className="btn-primary flex-1"
                  >
                    {isUploading ? (
                      <LoadingSpinner size="small" text="Uploading..." />
                    ) : (
                      'Upload File'
                    )}
                  </button>
                )}

                {selectedFile.temp_path && (
                  <button
                    onClick={handleTranscribe}
                    disabled={isTranscribing}
                    className="btn-primary flex-1"
                  >
                    {isTranscribing ? (
                      <LoadingSpinner size="small" text={transcriptionProgress || "Transcribing..."} />
                    ) : (
                      'Start Transcription'
                    )}
                  </button>
                )}
              </div>

              {/* Progress indicator */}
              {isTranscribing && transcriptionProgress && (
                <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center space-x-3">
                    <div className="flex-shrink-0">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-blue-900">{transcriptionProgress}</p>
                      <p className="text-xs text-blue-700 mt-1">
                        This may take several minutes. You'll be redirected when complete.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-600">{error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default HomePage;
