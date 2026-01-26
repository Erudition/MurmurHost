import React, { useCallback, useState } from 'react';
import { Upload, File, X } from 'lucide-react';
import { formatFileSize } from '../utils/formatters';

const UploadZone = ({ onFileSelect, isUploading, supportedFormats }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState('');

  const validateFile = (file) => {
    const maxSize = 100 * 1024 * 1024; // 100MB
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    
    if (file.size > maxSize) {
      return `File too large. Maximum size is ${formatFileSize(maxSize)}`;
    }
    
    if (!supportedFormats.includes(fileExt)) {
      return `Unsupported file format. Supported: ${supportedFormats.join(', ')}`;
    }
    
    return null;
  };

  const handleFile = useCallback((file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    
    setError('');
    setSelectedFile(file);
    onFileSelect(file);
  }, [onFileSelect, supportedFormats]);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, [handleFile]);

  const handleChange = useCallback((e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  }, [handleFile]);

  const removeFile = () => {
    setSelectedFile(null);
    setError('');
    onFileSelect(null);
  };

  return (
    <div className="w-full">
      <div
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors duration-200 ${
          dragActive
            ? 'border-primary-500 bg-primary-50'
            : selectedFile
            ? 'border-green-500 bg-green-50'
            : 'border-gray-300 hover:border-gray-400'
        } ${isUploading ? 'pointer-events-none opacity-50' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          onChange={handleChange}
          accept={supportedFormats.join(',')}
          disabled={isUploading}
        />
        
        {selectedFile ? (
          <div className="space-y-4">
            <div className="flex items-center justify-center space-x-3">
              <File className="w-8 h-8 text-green-600" />
              <div className="text-left">
                <p className="font-medium text-gray-900">{selectedFile.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
              </div>
              <button
                onClick={removeFile}
                className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                disabled={isUploading}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Upload className="w-12 h-12 text-gray-400 mx-auto" />
            <div>
              <p className="text-lg font-medium text-gray-900">
                Drop your audio or video file here
              </p>
              <p className="text-sm text-gray-500 mt-1">
                or click to browse files
              </p>
              <p className="text-xs text-gray-400 mt-2">
                Supported formats: {supportedFormats.join(', ')} • Max size: 100MB
              </p>
            </div>
          </div>
        )}
      </div>
      
      {error && (
        <div className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-2">
          {error}
        </div>
      )}
    </div>
  );
};

export default UploadZone;
