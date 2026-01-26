import React, { useState } from 'react';
import { Bot, Loader2, ChevronDown, ChevronUp, RotateCcw } from 'lucide-react';
import { summarizeTranscription } from '../services/api';
import { formatText } from '../utils/formatters';

const SummaryPanel = ({ transcriptionId, transcriptionText, summaryText, summaryModel }) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [summary, setSummary] = useState(summaryText);
  const [model, setModel] = useState(summaryModel);

  const handleGenerateSummary = async () => {
    if (!transcriptionId || !transcriptionText) return;
    
    setIsGenerating(true);
    try {
      const result = await summarizeTranscription(transcriptionId, transcriptionText);
      setSummary(result.summary_text);
      setModel(result.summary_model);
    } catch (error) {
      console.error('Error generating summary:', error);
      alert('Failed to generate summary. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  if (!summary && !isGenerating) {
    return (
      <div className="mt-4 p-4 bg-gray-50 rounded-lg border">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bot className="w-5 h-5 text-gray-600" />
            <span className="font-medium text-gray-700">AI Summary</span>
          </div>
          <button
            onClick={handleGenerateSummary}
            className="btn-primary text-sm"
            disabled={isGenerating}
          >
            Generate Summary
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4 bg-gray-50 rounded-lg border">
      <div className="p-4 flex items-center justify-between">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center space-x-2 hover:bg-gray-100 transition-colors flex-1"
        >
          <Bot className="w-5 h-5 text-gray-600" />
          <span className="font-medium text-gray-700">AI Summary</span>
          {model && (
            <span className="text-xs text-gray-500 bg-gray-200 px-2 py-1 rounded">
              {model}
            </span>
          )}
        </button>
        <div className="flex items-center space-x-2">
          <button
            onClick={handleGenerateSummary}
            disabled={isGenerating}
            className="flex items-center space-x-1 text-sm text-primary-600 hover:text-primary-700 px-2 py-1 rounded hover:bg-primary-50 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Regenerate summary"
          >
            <RotateCcw className="w-4 h-4" />
            <span className="hidden sm:inline">Regenerate</span>
          </button>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          )}
        </div>
      </div>
      
      {isExpanded && (
        <div className="px-4 pb-4">
          {isGenerating ? (
            <div className="flex items-center space-x-2 py-4">
              <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
              <span className="text-gray-600">Generating summary...</span>
            </div>
          ) : summary ? (
            <div className="space-y-3">
              <div className="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
                <div className="prose prose-sm max-w-none">
                  <div className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {formatText(summary)}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2 pt-2">
                <button
                  onClick={handleGenerateSummary}
                  disabled={isGenerating}
                  className="flex items-center space-x-1 text-sm text-primary-600 hover:text-primary-700 underline disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Regenerate Summary</span>
                </button>
                {model && (
                  <span className="text-xs text-gray-500">
                    Generated with {model}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <p className="text-gray-500 italic">No summary available</p>
          )}
        </div>
      )}
    </div>
  );
};

export default SummaryPanel;
