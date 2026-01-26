import React, { useState, useEffect } from 'react';
import { Search, RefreshCw } from 'lucide-react';
import { getTranscriptions } from '../services/api';
import TranscriptionCard from './TranscriptionCard';
import LoadingSpinner from './LoadingSpinner';

const TranscriptionList = ({ refreshTrigger, onRefresh }) => {
  const [transcriptions, setTranscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [error, setError] = useState('');

  const perPage = 10;

  const fetchTranscriptions = async (page = 1, search = '') => {
    try {
      setLoading(true);
      setError('');
      const response = await getTranscriptions(page, perPage, search);
      setTranscriptions(response.transcriptions);
      setPagination(response.pagination);
    } catch (error) {
      console.error('Error fetching transcriptions:', error);
      setError('Failed to load transcriptions. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTranscriptions(currentPage, searchTerm);
  }, [currentPage, searchTerm, refreshTrigger]);

  const handleSearch = (e) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchTranscriptions(1, searchTerm);
  };

  const handleRefresh = () => {
    fetchTranscriptions(currentPage, searchTerm);
    if (onRefresh) {
      onRefresh();
    }
  };

  const handleDelete = (deletedId) => {
    setTranscriptions(transcriptions.filter(t => t.id !== deletedId));
  };

  const handleUpdate = (updatedTranscription) => {
    setTranscriptions(transcriptions.map(t => 
      t.id === updatedTranscription.id ? updatedTranscription : t
    ));
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
  };

  if (loading && transcriptions.length === 0) {
    return (
      <div className="flex justify-center items-center py-12">
        <LoadingSpinner text="Loading transcriptions..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Transcriptions</h2>
        <button
          onClick={handleRefresh}
          className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      <form onSubmit={handleSearch} className="flex space-x-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search transcriptions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="input-field pl-10"
          />
        </div>
        <button type="submit" className="btn-primary">
          Search
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">{error}</p>
        </div>
      )}

      {transcriptions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">No transcriptions found</p>
          <p className="text-gray-400 mt-2">
            {searchTerm ? 'Try adjusting your search terms' : 'Upload a file to get started'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {transcriptions.map((transcription) => (
            <TranscriptionCard
              key={transcription.id}
              transcription={transcription}
              onDelete={handleDelete}
              onUpdate={handleUpdate}
            />
          ))}
        </div>
      )}

      {pagination && pagination.pages > 1 && (
        <div className="flex items-center justify-center space-x-2">
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          
          <span className="text-sm text-gray-600">
            Page {currentPage} of {pagination.pages}
          </span>
          
          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage === pagination.pages}
            className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default TranscriptionList;
