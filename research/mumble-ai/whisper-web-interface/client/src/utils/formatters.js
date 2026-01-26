export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const formatDuration = (seconds) => {
  if (!seconds) return 'Unknown';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  } else {
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
};

export const formatDate = (dateString) => {
  if (!dateString) return 'Unknown';
  
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatLanguage = (language, probability) => {
  if (!language || typeof language !== 'string') return 'Unknown';
  
  const langNames = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
    'ar': 'Arabic',
    'hi': 'Hindi',
  };
  
  const langName = langNames[language] || language.toUpperCase();
  const confidence = probability ? ` (${Math.round(probability * 100)}%)` : '';
  
  return `${langName}${confidence}`;
};

export const formatText = (text) => {
  if (!text) return '';

  // Improve text formatting for better readability
  return text
    .split(/\n+/) // Split by line breaks
    .map(paragraph => paragraph.trim()) // Trim each paragraph
    .filter(paragraph => paragraph.length > 0) // Remove empty paragraphs
    .join('\n\n'); // Join with double line breaks for clear separation
};

export const formatTimestamp = (seconds) => {
  if (typeof seconds !== 'number') return '0:00';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
};

export const formatSegmentText = (segments) => {
  if (!segments || !Array.isArray(segments)) return '';

  let result = [];
  let currentSpeaker = null;
  let currentBlock = [];

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const timestamp = formatTimestamp(seg.start);
    const speaker = seg.speaker || 'Speaker 1';

    if (speaker !== currentSpeaker) {
      // Save previous speaker's block
      if (currentBlock.length > 0 && currentSpeaker) {
        result.push({
          speaker: currentSpeaker,
          segments: currentBlock
        });
      }

      // Start new speaker block
      currentSpeaker = speaker;
      currentBlock = [{ timestamp, text: seg.text }];
    } else {
      // Continue current speaker's block
      currentBlock.push({ timestamp, text: seg.text });
    }
  }

  // Add final block
  if (currentBlock.length > 0 && currentSpeaker) {
    result.push({
      speaker: currentSpeaker,
      segments: currentBlock
    });
  }

  // Format as readable conversation
  return result.map(block => {
    const firstTimestamp = block.segments[0].timestamp;
    const speakerLine = `${block.speaker} (${firstTimestamp})`;
    const textLines = block.segments.map(s => s.text.trim()).join(' ');
    return `${speakerLine}\n${textLines}`;
  }).join('\n\n');
};

export const getSpeakerCount = (segments) => {
  if (!segments || !Array.isArray(segments)) return 0;
  const speakers = new Set(segments.map(s => s.speaker));
  return speakers.size;
};

export const getSpeakerColor = (speaker) => {
  const colors = {
    'Speaker 1': 'bg-blue-100 text-blue-800',
    'Speaker 2': 'bg-green-100 text-green-800',
    'Speaker 3': 'bg-purple-100 text-purple-800',
    'Speaker 4': 'bg-orange-100 text-orange-800',
    'Speaker 5': 'bg-pink-100 text-pink-800',
  };
  return colors[speaker] || 'bg-gray-100 text-gray-800';
};