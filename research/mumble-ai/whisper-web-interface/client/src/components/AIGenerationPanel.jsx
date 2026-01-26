import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles, FileText, List, Target, CheckSquare, ListOrdered, FileCheck, MessageSquare, Loader2, TrendingUp, FileSearch, Calendar, Scale, FileSignature, Download } from 'lucide-react';
import { generateAIContent, getAIContent } from '../services/api';

const AIGenerationPanel = ({ transcriptionText, transcriptionId }) => {
  const [generating, setGenerating] = useState(false);
  const [currentType, setCurrentType] = useState(null);
  const [generatedContent, setGeneratedContent] = useState({});
  const [expandedType, setExpandedType] = useState(null);
  const [loading, setLoading] = useState(true);

  const generationOptions = [
    {
      type: 'brief_summary',
      label: 'Brief Summary',
      description: '1-2 paragraph concise summary',
      icon: FileText,
      color: 'blue'
    },
    {
      type: 'detailed_summary',
      label: 'Detailed Summary',
      description: 'Comprehensive summary with all details',
      icon: FileCheck,
      color: 'indigo'
    },
    {
      type: 'bullet_points',
      label: 'Bullet Points',
      description: 'Key points in bullet format',
      icon: List,
      color: 'green'
    },
    {
      type: 'key_takeaways',
      label: 'Key Takeaways',
      description: '5-10 most important insights',
      icon: Target,
      color: 'purple'
    },
    {
      type: 'action_items',
      label: 'Action Items',
      description: 'Extract tasks and next steps',
      icon: CheckSquare,
      color: 'orange'
    },
    {
      type: 'outline',
      label: 'Outline',
      description: 'Hierarchical structure outline',
      icon: ListOrdered,
      color: 'teal'
    },
    {
      type: 'meeting_notes',
      label: 'Meeting Notes',
      description: 'Structured meeting notes format',
      icon: FileText,
      color: 'pink'
    },
    {
      type: 'qa_format',
      label: 'Q&A Format',
      description: 'Questions and answers extracted',
      icon: MessageSquare,
      color: 'cyan'
    },
    {
      type: 'executive_summary',
      label: 'Executive Summary',
      description: 'High-level overview for leadership',
      icon: TrendingUp,
      color: 'red'
    },
    {
      type: 'sop',
      label: 'SOP Document',
      description: 'Standard Operating Procedure',
      icon: FileSignature,
      color: 'amber'
    },
    {
      type: 'timeline',
      label: 'Timeline',
      description: 'Chronological event timeline',
      icon: Calendar,
      color: 'lime'
    },
    {
      type: 'topics_tags',
      label: 'Topics & Tags',
      description: 'Main topics and themes extracted',
      icon: FileSearch,
      color: 'emerald'
    },
    {
      type: 'pros_cons',
      label: 'Pros & Cons',
      description: 'Pros and cons analysis',
      icon: Scale,
      color: 'violet'
    },
    {
      type: 'decisions_log',
      label: 'Decisions Log',
      description: 'All decisions documented',
      icon: FileCheck,
      color: 'fuchsia'
    }
  ];

  // Load saved content on mount
  useEffect(() => {
    const loadSavedContent = async () => {
      if (!transcriptionId) {
        setLoading(false);
        return;
      }

      try {
        const result = await getAIContent(transcriptionId);
        if (result.success && result.content) {
          setGeneratedContent(result.content);
        }
      } catch (error) {
        console.error('Error loading saved AI content:', error);
      } finally {
        setLoading(false);
      }
    };

    loadSavedContent();
  }, [transcriptionId]);

  const handleGenerate = async (type) => {
    if (!transcriptionText) {
      alert('No transcription text available');
      return;
    }

    if (!window.confirm(`Generate ${generationOptions.find(o => o.type === type)?.label}? This may take up to 5 minutes.`)) {
      return;
    }

    setGenerating(true);
    setCurrentType(type);

    try {
      const result = await generateAIContent(transcriptionText, type, transcriptionId);
      setGeneratedContent(prev => ({
        ...prev,
        [type]: {
          content: result.content,
          model: result.model
        }
      }));
      setExpandedType(type);
      alert('AI generation completed successfully!');
    } catch (error) {
      console.error('Error generating AI content:', error);
      alert(`Failed to generate content: ${error.response?.data?.error || error.message}`);
    } finally {
      setGenerating(false);
      setCurrentType(null);
    }
  };

  const handleExportAIContent = (type, format) => {
    const url = `/api/export-ai-content/${transcriptionId}/${type}/${format}`;
    window.open(url, '_blank');
  };

  const getColorClasses = (color) => {
    const colors = {
      blue: 'bg-blue-600 hover:bg-blue-700 text-white',
      indigo: 'bg-indigo-600 hover:bg-indigo-700 text-white',
      green: 'bg-green-600 hover:bg-green-700 text-white',
      purple: 'bg-purple-600 hover:bg-purple-700 text-white',
      orange: 'bg-orange-600 hover:bg-orange-700 text-white',
      teal: 'bg-teal-600 hover:bg-teal-700 text-white',
      pink: 'bg-pink-600 hover:bg-pink-700 text-white',
      cyan: 'bg-cyan-600 hover:bg-cyan-700 text-white',
      red: 'bg-red-600 hover:bg-red-700 text-white',
      amber: 'bg-amber-600 hover:bg-amber-700 text-white',
      lime: 'bg-lime-600 hover:bg-lime-700 text-white',
      emerald: 'bg-emerald-600 hover:bg-emerald-700 text-white',
      violet: 'bg-violet-600 hover:bg-violet-700 text-white',
      fuchsia: 'bg-fuchsia-600 hover:bg-fuchsia-700 text-white'
    };
    return colors[color] || colors.blue;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-purple-600 mr-3" />
          <span>Loading AI content...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center mb-6">
        <Sparkles className="w-6 h-6 text-purple-600 mr-3" />
        <div>
          <h2 className="text-xl font-semibold text-gray-900">AI Generation Options</h2>
          <p className="text-sm text-gray-500">Generate various AI-powered content from your transcription (saved automatically)</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        {generationOptions.map((option) => {
          const Icon = option.icon;
          const isGenerating = generating && currentType === option.type;
          const hasContent = generatedContent[option.type];

          return (
            <div key={option.type} className="relative">
              <button
                onClick={() => handleGenerate(option.type)}
                disabled={generating}
                className={`w-full p-3 rounded-lg transition-all duration-200 ${
                  getColorClasses(option.color)
                } disabled:opacity-50 disabled:cursor-not-allowed flex flex-col items-start text-left ${
                  hasContent ? 'ring-2 ring-offset-2 ring-green-500' : ''
                }`}
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <Icon className={`w-4 h-4 ${isGenerating ? 'animate-spin' : ''}`} />
                  {hasContent && !isGenerating && (
                    <CheckSquare className="w-3 h-3" />
                  )}
                  {isGenerating && (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  )}
                </div>
                <div className="font-semibold text-xs mb-1">{option.label}</div>
                <div className="text-[10px] opacity-90">{option.description}</div>
              </button>
            </div>
          );
        })}
      </div>

      {/* Display generated content */}
      {Object.keys(generatedContent).length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Generated Content</h3>
          {Object.entries(generatedContent).map(([type, data]) => {
            const option = generationOptions.find(o => o.type === type);
            const isExpanded = expandedType === type;

            return (
              <div key={type} className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedType(isExpanded ? null : type)}
                  className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors flex items-center justify-between"
                >
                  <div className="flex items-center">
                    {React.createElement(option.icon, { className: 'w-5 h-5 mr-2 text-gray-600' })}
                    <span className="font-semibold text-gray-900">{option.label}</span>
                    {data.model && (
                      <span className="ml-2 text-xs text-gray-500 bg-gray-200 px-2 py-1 rounded">
                        {data.model}
                      </span>
                    )}
                  </div>
                  <svg
                    className={`w-5 h-5 text-gray-500 transition-transform ${
                      isExpanded ? 'transform rotate-180' : ''
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {isExpanded && (
                  <div className="p-4 bg-white">
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {data.content}
                      </ReactMarkdown>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(data.content)}
                        className="text-sm text-blue-600 hover:text-blue-700 underline"
                      >
                        Copy to Clipboard
                      </button>
                      <button
                        onClick={() => handleGenerate(type)}
                        disabled={generating}
                        className="text-sm text-purple-600 hover:text-purple-700 underline disabled:opacity-50"
                      >
                        Regenerate
                      </button>
                      <button
                        onClick={() => handleExportAIContent(type, 'docx')}
                        className="flex items-center gap-1 text-sm text-green-600 hover:text-green-700 underline"
                      >
                        <Download className="w-3 h-3" />
                        Export Word
                      </button>
                      <button
                        onClick={() => handleExportAIContent(type, 'pdf')}
                        className="flex items-center gap-1 text-sm text-red-600 hover:text-red-700 underline"
                      >
                        <Download className="w-3 h-3" />
                        Export PDF
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {generating && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600 mr-3" />
            <div>
              <div className="font-semibold text-blue-900">
                Generating {generationOptions.find(o => o.type === currentType)?.label}...
              </div>
              <div className="text-sm text-blue-700">
                This may take up to 5 minutes. Please wait...
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIGenerationPanel;
