import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Clock, Globe, Users, ChevronLeft, ChevronRight, Search, Trash2 } from 'lucide-react';
import { getTranscriptions, deleteTranscription } from '../services/api';
import { formatFileSize, formatDuration, formatDate, formatLanguage, getSpeakerCount } from '../utils/formatters';
import LoadingSpinner from '../components/LoadingSpinner';

function HistoryPage() {
  const navigate = useNavigate();
  const [transcriptions, setTranscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, per_page: 10, total: 0, pages: 0 });
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  useEffect(() => {
    loadTranscriptions();
  }, [pagination.page, search]);

  const loadTranscriptions = async () => {
    try {
      setLoading(true);
      const data = await getTranscriptions(pagination.page, pagination.per_page, search);
      setTranscriptions(data.transcriptions || []);
      setPagination(data.pagination);
    } catch (err) {
      console.error('Error loading transcriptions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    setSearch(searchInput);
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handleDelete = async (id, title) => {
    if (!window.confirm(`Are you sure you want to delete "${title}"?`)) {
      return;
    }

    try {
      await deleteTranscription(id);
      loadTranscriptions();
    } catch (err) {
      console.error('Error deleting transcription:', err);
      alert('Failed to delete transcription');
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= pagination.pages) {
      setPagination(prev => ({ ...prev, page: newPage }));
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Transcription History</h1>

          {/* Search Bar */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search transcriptions..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button type="submit" className="btn-primary">
              Search
            </button>
            {search && (
              <button
                type="button"
                onClick={() => {
                  setSearch('');
                  setSearchInput('');
                }}
                className="btn-secondary"
              >
                Clear
              </button>
            )}
          </form>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner text="Loading transcriptions..." />
          </div>
        ) : transcriptions.length === 0 ? (
          /* Empty State */
          <div className="text-center py-12">
            <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No transcriptions found</h3>
            <p className="text-gray-600 mb-6">
              {search ? 'Try a different search term' : 'Upload your first audio or video file to get started'}
            </p>
            <button onClick={() => navigate('/')} className="btn-primary">
              Upload File
            </button>
          </div>
        ) : (
          <>
            {/* Transcription Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {transcriptions.map((transcription) => (
                <div
                  key={transcription.id}
                  className="bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow duration-200 overflow-hidden group cursor-pointer"
                  onClick={() => navigate(`/transcription/${transcription.id}`)}
                >
                  {/* Card Header */}
                  <div className="p-5 border-b border-gray-100">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
                          {transcription.title || transcription.filename}
                        </h3>
                        {transcription.title && (
                          <p className="text-xs text-gray-500 truncate mt-1">
                            {transcription.filename}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(transcription.id, transcription.title || transcription.filename);
                        }}
                        className="ml-2 p-1 text-gray-400 hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="flex flex-wrap gap-2 text-xs text-gray-600">
                      <span className="bg-gray-100 px-2 py-1 rounded">
                        {transcription.original_format?.toUpperCase()}
                      </span>
                      <span className="flex items-center">
                        <Clock className="w-3 h-3 mr-1" />
                        {formatDuration(transcription.duration_seconds)}
                      </span>
                      <span className="flex items-center">
                        <Globe className="w-3 h-3 mr-1" />
                        {transcription.language?.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Card Body - Preview */}
                  <div className="p-5">
                    <p className="text-sm text-gray-700 line-clamp-3 mb-3">
                      {transcription.transcription_text}
                    </p>

                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span>{formatDate(transcription.created_at)}</span>
                      {transcription.transcription_segments && getSpeakerCount(transcription.transcription_segments) > 1 && (
                        <span className="flex items-center">
                          <Users className="w-3 h-3 mr-1" />
                          {getSpeakerCount(transcription.transcription_segments)} speakers
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Card Footer - Summary Badge */}
                  {transcription.summary_text && (
                    <div className="px-5 pb-4">
                      <span className="inline-flex items-center text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                        <FileText className="w-3 h-3 mr-1" />
                        Summary available
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Pagination */}
            {pagination.pages > 1 && (
              <div className="flex items-center justify-between bg-white rounded-lg shadow-md px-6 py-4">
                <div className="text-sm text-gray-700">
                  Showing <span className="font-medium">{((pagination.page - 1) * pagination.per_page) + 1}</span> to{' '}
                  <span className="font-medium">{Math.min(pagination.page * pagination.per_page, pagination.total)}</span> of{' '}
                  <span className="font-medium">{pagination.total}</span> results
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handlePageChange(pagination.page - 1)}
                    disabled={pagination.page === 1}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>

                  <div className="flex space-x-1">
                    {[...Array(pagination.pages)].map((_, i) => {
                      const page = i + 1;
                      // Show first, last, current, and adjacent pages
                      if (
                        page === 1 ||
                        page === pagination.pages ||
                        (page >= pagination.page - 1 && page <= pagination.page + 1)
                      ) {
                        return (
                          <button
                            key={page}
                            onClick={() => handlePageChange(page)}
                            className={`px-3 py-1 rounded-lg transition-colors ${
                              page === pagination.page
                                ? 'bg-blue-600 text-white'
                                : 'hover:bg-gray-100 text-gray-700'
                            }`}
                          >
                            {page}
                          </button>
                        );
                      } else if (page === pagination.page - 2 || page === pagination.page + 2) {
                        return <span key={page} className="px-2">...</span>;
                      }
                      return null;
                    })}
                  </div>

                  <button
                    onClick={() => handlePageChange(pagination.page + 1)}
                    disabled={pagination.page === pagination.pages}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default HistoryPage;
