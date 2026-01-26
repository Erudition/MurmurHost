class TTSApp {
    constructor() {
        this.voices = {};
        this.selectedVoice = null;
        this.selectedEngine = 'piper';
        this.audioContext = null;
        this.currentReferenceAudio = null;
        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadVoices();
        this.populateRegionFilter();
        this.updateCharCount();
        this.updateEngineUI();
    }

    setupEventListeners() {
        // Text input
        const textInput = document.getElementById('text-input');
        textInput.addEventListener('input', () => {
            this.updateCharCount();
            this.updateButtonStates();
        });

        // Character count
        textInput.addEventListener('input', this.updateCharCount.bind(this));

        // Engine selection
        document.querySelectorAll('input[name="engine"]').forEach(radio => {
            radio.addEventListener('change', async (e) => {
                this.selectedEngine = e.target.value;
                this.clearSelection();
                await this.loadVoices();
                this.populateRegionFilter();
                this.updateEngineUI();
                const engineName = e.target.value === 'piper' ? 'Piper' : 
                                  e.target.value === 'silero' ? 'Silero' : 'Chatterbox';
                this.showStatus(`Switched to ${engineName} TTS engine`, 'success');
            });
        });

        // Voice cloning event listeners
        this.setupVoiceCloningListeners();

        // Filter controls
        document.getElementById('region-filter').addEventListener('change', this.filterVoices.bind(this));
        document.getElementById('gender-filter').addEventListener('change', this.filterVoices.bind(this));
        document.getElementById('quality-filter').addEventListener('change', this.filterVoices.bind(this));

        // Buttons
        document.getElementById('preview-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.previewVoice();
        });
        document.getElementById('generate-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.generateAudio();
        });

        // Audio player
        const audioPlayer = document.getElementById('audio-player');
        audioPlayer.addEventListener('loadedmetadata', () => {
            const duration = this.formatTime(audioPlayer.duration);
            document.getElementById('audio-duration').textContent = duration;
        });
    }

    async loadVoices() {
        try {
            const response = await fetch(`/api/voices?engine=${this.selectedEngine}`);
            if (!response.ok) {
                throw new Error('Failed to load voices');
            }
            const data = await response.json();
            
            // Handle Chatterbox format differently
            if (this.selectedEngine === 'chatterbox') {
                this.voices = data.voices || [];
            } else {
                this.voices = data;
            }
            
            this.renderVoices();
        } catch (error) {
            this.showStatus('Failed to load voices: ' + error.message, 'error');
            console.error('Error loading voices:', error);
        }
    }

    populateRegionFilter() {
        const regionFilter = document.getElementById('region-filter');
        // Clear existing options except the first "All Regions" option
        while (regionFilter.options.length > 1) {
            regionFilter.remove(1);
        }
        
        // Skip for Chatterbox (no regions)
        if (this.selectedEngine === 'chatterbox') {
            return;
        }
        
        // Add new options for Piper/Silero
        if (this.voices && typeof this.voices === 'object') {
            Object.keys(this.voices).forEach(regionCode => {
                const option = document.createElement('option');
                option.value = regionCode;
                option.textContent = this.voices[regionCode].name;
                regionFilter.appendChild(option);
            });
        }
    }

    renderVoices() {
        const voiceGrid = document.getElementById('voice-grid');
        voiceGrid.innerHTML = '';

        if (this.selectedEngine === 'chatterbox') {
            // Render cloned voices
            this.renderClonedVoices();
        } else {
            // Render Piper/Silero voices
            if (this.voices && typeof this.voices === 'object') {
                Object.entries(this.voices).forEach(([regionCode, regionData]) => {
                    if (regionData && regionData.voices) {
                        Object.entries(regionData.voices).forEach(([gender, voiceList]) => {
                            if (Array.isArray(voiceList)) {
                                voiceList.forEach(voice => {
                                    const voiceCard = this.createVoiceCard(voice, regionData.name, gender);
                                    voiceGrid.appendChild(voiceCard);
                                });
                            }
                        });
                    }
                });
            }
        }
    }

    renderClonedVoices() {
        const clonedVoicesGrid = document.getElementById('cloned-voices-grid');
        if (!clonedVoicesGrid) return;
        
        clonedVoicesGrid.innerHTML = '';
        
        if (!Array.isArray(this.voices) || this.voices.length === 0) {
            clonedVoicesGrid.innerHTML = '<p style="text-align: center; color: #718096; padding: 20px;">No cloned voices yet. Upload an audio file above to get started!</p>';
            return;
        }
        
        this.voices.forEach(voice => {
            const voiceCard = this.createClonedVoiceCard(voice);
            clonedVoicesGrid.appendChild(voiceCard);
        });
    }

    createClonedVoiceCard(voice) {
        const card = document.createElement('div');
        card.className = 'voice-card cloned-voice-card';
        card.dataset.voiceId = voice.id;
        
        card.innerHTML = `
            <div class="voice-name">${voice.name}</div>
            <div class="voice-details">
                <span>${voice.language || 'en'}</span>
                ${voice.description ? `<span class="voice-description">${voice.description}</span>` : ''}
            </div>
            <button class="delete-voice-btn" onclick="event.stopPropagation(); ttsApp.deleteClonedVoice(${voice.id})">×</button>
        `;
        
        card.addEventListener('click', () => this.selectVoice(voice, card));
        return card;
    }

    createVoiceCard(voice, regionName, gender) {
        const card = document.createElement('div');
        card.className = 'voice-card';
        card.dataset.voiceId = voice.id;
        card.dataset.region = regionName;
        card.dataset.gender = gender;
        card.dataset.quality = voice.quality;

        card.innerHTML = `
            <div class="voice-name">${voice.name}</div>
            <div class="voice-details">
                <span>${regionName}</span>
                <span class="voice-quality quality-${voice.quality}">${voice.quality}</span>
            </div>
        `;

        card.addEventListener('click', () => this.selectVoice(voice, card));
        return card;
    }

    selectVoice(voice, cardElement) {
        // Remove previous selection
        document.querySelectorAll('.voice-card').forEach(card => {
            card.classList.remove('selected');
        });

        // Select new voice
        cardElement.classList.add('selected');
        this.selectedVoice = voice;
        
        // Update selected voice name in audio section
        document.getElementById('selected-voice-name').textContent = voice.name;
        
        this.updateButtonStates();
        this.showStatus(`Selected voice: ${voice.name}`, 'success');
    }

    filterVoices() {
        const regionFilter = document.getElementById('region-filter').value;
        const genderFilter = document.getElementById('gender-filter').value;
        const qualityFilter = document.getElementById('quality-filter').value;

        const voiceCards = document.querySelectorAll('.voice-card');
        
        voiceCards.forEach(card => {
            let show = true;

            if (regionFilter && card.dataset.region !== this.voices[regionFilter]?.name) {
                show = false;
            }

            if (genderFilter && card.dataset.gender !== genderFilter) {
                show = false;
            }

            if (qualityFilter && card.dataset.quality !== qualityFilter) {
                show = false;
            }

            card.style.display = show ? 'block' : 'none';
        });

        // Clear selection if selected voice is hidden
        if (this.selectedVoice) {
            const selectedCard = document.querySelector('.voice-card.selected');
            if (selectedCard && selectedCard.style.display === 'none') {
                this.clearSelection();
            }
        }
    }

    clearSelection() {
        document.querySelectorAll('.voice-card').forEach(card => {
            card.classList.remove('selected');
        });
        this.selectedVoice = null;
        this.updateButtonStates();
    }

    updateCharCount() {
        const textInput = document.getElementById('text-input');
        const charCount = document.getElementById('char-count');
        const count = textInput.value.length;
        charCount.textContent = count;
        
        if (count > 4500) {
            charCount.style.color = '#e53e3e';
        } else if (count > 4000) {
            charCount.style.color = '#dd6b20';
        } else {
            charCount.style.color = '#718096';
        }
    }

    updateButtonStates() {
        const textInput = document.getElementById('text-input');
        const hasText = textInput.value.trim().length > 0;
        const hasVoice = this.selectedVoice !== null;

        document.getElementById('preview-btn').disabled = !hasVoice;
        document.getElementById('generate-btn').disabled = !hasText || !hasVoice;
    }

    async previewVoice() {
        if (!this.selectedVoice) {
            this.showStatus('Please select a voice first', 'error');
            return;
        }

        const previewText = "Hello! This is a preview of this voice. How does it sound?";
        await this.generateAudio(previewText, true);
    }

    async generateAudio(customText = null, isPreview = false) {
        const textInput = document.getElementById('text-input');
        const text = customText || textInput.value.trim();

        console.log('Text input element:', textInput);
        console.log('Text input value:', textInput.value);
        console.log('Text after trim:', text);
        console.log('Text type:', typeof text);

        if (!text) {
            this.showStatus('Please enter some text', 'error');
            return;
        }

        if (!this.selectedVoice) {
            this.showStatus('Please select a voice', 'error');
            return;
        }

        this.showLoading(true);
        this.showStatus(isPreview ? 'Generating preview...' : 'Generating audio...', 'info');

        try {
            const payload = {
                text: text,
                voice: this.selectedVoice.id,
                engine: this.selectedEngine
            };
            console.log('Sending payload:', payload);

            const response = await fetch('/api/synthesize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to generate audio');
            }

            // Create audio blob and play
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            
            const audioPlayer = document.getElementById('audio-player');
            audioPlayer.src = audioUrl;
            
            // Show audio section
            document.getElementById('audio-section').style.display = 'block';
            
            // Auto-play for preview
            if (isPreview) {
                audioPlayer.play();
            }

            this.showStatus(
                isPreview ? 'Preview generated successfully!' : 'Audio generated successfully! Click play to listen.',
                'success'
            );

            // Clean up old URL after 5 minutes
            setTimeout(() => {
                URL.revokeObjectURL(audioUrl);
            }, 300000);

        } catch (error) {
            this.showStatus('Error: ' + error.message, 'error');
            console.error('Audio generation error:', error);
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        if (show) {
            overlay.classList.add('show');
        } else {
            overlay.classList.remove('show');
        }
    }

    showStatus(message, type = 'info') {
        const statusElement = document.getElementById('status-message');
        statusElement.textContent = message;
        statusElement.className = `status-message status-${type}`;
        
        // Auto-hide success messages after 3 seconds
        if (type === 'success') {
            setTimeout(() => {
                statusElement.textContent = '';
                statusElement.className = 'status-message';
            }, 3000);
        }
    }

    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    updateEngineUI() {
        const voiceCloningSection = document.getElementById('voice-cloning-section');
        const filterSection = document.querySelector('.filter-section');
        
        if (this.selectedEngine === 'chatterbox') {
            if (voiceCloningSection) voiceCloningSection.style.display = 'block';
            if (filterSection) filterSection.style.display = 'none';
        } else {
            if (voiceCloningSection) voiceCloningSection.style.display = 'none';
            if (filterSection) filterSection.style.display = 'block';
        }
    }

    setupVoiceCloningListeners() {
        const cloneAudioInput = document.getElementById('clone-audio-file');
        const testCloneBtn = document.getElementById('test-clone-btn');
        const saveCloneBtn = document.getElementById('save-clone-btn');
        const saveVoiceModal = document.getElementById('save-voice-modal');
        const closeModal = document.getElementById('close-modal');
        const cancelSave = document.getElementById('cancel-save');
        const confirmSave = document.getElementById('confirm-save');

        // File upload with drag and drop support
        const fileUploadBox = document.querySelector('.file-upload-box');
        const fileInfo = document.getElementById('file-info');
        const fileName = document.getElementById('file-name');
        const removeFileBtn = document.getElementById('remove-file');

        // Audio file input change handler
        if (cloneAudioInput) {
            cloneAudioInput.addEventListener('change', (e) => {
                this.handleReferenceAudioUpload(e);
            });
        }

        // Drag and drop handlers
        if (fileUploadBox) {
            fileUploadBox.addEventListener('dragover', (e) => {
                e.preventDefault();
                fileUploadBox.classList.add('dragover');
            });

            fileUploadBox.addEventListener('dragleave', () => {
                fileUploadBox.classList.remove('dragover');
            });

            fileUploadBox.addEventListener('drop', (e) => {
                e.preventDefault();
                fileUploadBox.classList.remove('dragover');

                const files = e.dataTransfer.files;
                if (files.length > 0 && files[0].type.startsWith('audio/')) {
                    cloneAudioInput.files = files;
                    this.handleReferenceAudioUpload({ target: { files: files } });
                }
            });
        }

        // Remove file button
        if (removeFileBtn) {
            removeFileBtn.addEventListener('click', () => {
                this.currentReferenceAudio = null;
                if (cloneAudioInput) cloneAudioInput.value = '';
                if (fileInfo) fileInfo.style.display = 'none';
                if (fileUploadBox) fileUploadBox.querySelector('.file-upload-label').style.display = 'flex';
                if (testCloneBtn) testCloneBtn.disabled = true;
                if (saveCloneBtn) saveCloneBtn.disabled = true;
            });
        }

        // Test voice button
        if (testCloneBtn) {
            testCloneBtn.addEventListener('click', () => this.testClonedVoice());
        }

        // Save voice button
        if (saveCloneBtn) {
            saveCloneBtn.addEventListener('click', () => {
                if (saveVoiceModal) saveVoiceModal.style.display = 'flex';
            });
        }

        // Modal close button
        if (closeModal) {
            closeModal.addEventListener('click', () => {
                if (saveVoiceModal) saveVoiceModal.style.display = 'none';
            });
        }

        // Cancel save button
        if (cancelSave) {
            cancelSave.addEventListener('click', () => {
                if (saveVoiceModal) saveVoiceModal.style.display = 'none';
            });
        }

        // Confirm save button
        if (confirmSave) {
            confirmSave.addEventListener('click', () => this.saveClonedVoice());
        }
    }

    handleReferenceAudioUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        this.currentReferenceAudio = file;

        // Show file info
        const fileInfo = document.getElementById('file-info');
        const fileName = document.getElementById('file-name');
        const fileUploadLabel = document.querySelector('.file-upload-label');

        if (fileInfo && fileName) {
            fileName.textContent = file.name;
            fileInfo.style.display = 'flex';
            if (fileUploadLabel) fileUploadLabel.style.display = 'none';
        }

        this.showStatus(`Audio file loaded: ${file.name}`, 'success');

        // Enable buttons
        const testBtn = document.getElementById('test-clone-btn');
        const saveBtn = document.getElementById('save-clone-btn');
        if (testBtn) testBtn.disabled = false;
        if (saveBtn) saveBtn.disabled = false;
    }

    async testClonedVoice() {
        if (!this.currentReferenceAudio) {
            this.showStatus('Please upload a reference audio file first', 'error');
            return;
        }
        
        this.showLoading(true);
        this.showStatus('Testing cloned voice...', 'info');
        
        try {
            const formData = new FormData();
            formData.append('audio', this.currentReferenceAudio);
            formData.append('text', 'Hello! This is a test of the cloned voice. How does it sound?');
            formData.append('language', document.getElementById('clone-language')?.value || 'en');
            
            const response = await fetch('/api/chatterbox/clone', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to clone voice');
            }
            
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            
            const audioPlayer = document.getElementById('audio-player');
            audioPlayer.src = audioUrl;
            document.getElementById('audio-section').style.display = 'block';
            audioPlayer.play();
            
            this.showStatus('Voice cloned successfully! Listen to the preview.', 'success');
            
            setTimeout(() => URL.revokeObjectURL(audioUrl), 300000);
        } catch (error) {
            this.showStatus('Error: ' + error.message, 'error');
            console.error('Voice cloning error:', error);
        } finally {
            this.showLoading(false);
        }
    }

    async saveClonedVoice() {
        if (!this.currentReferenceAudio) {
            this.showStatus('Please upload a reference audio file first', 'error');
            return;
        }

        const voiceName = document.getElementById('voice-name')?.value.trim();
        if (!voiceName) {
            this.showStatus('Please enter a voice name', 'error');
            return;
        }

        this.showLoading(true);
        this.showStatus('Saving cloned voice...', 'info');

        try {
            const formData = new FormData();
            formData.append('audio', this.currentReferenceAudio);
            formData.append('name', voiceName);
            formData.append('description', document.getElementById('voice-description')?.value || '');
            formData.append('language', document.getElementById('clone-language')?.value || 'en');

            // Parse tags from comma-separated string
            const tagsInput = document.getElementById('voice-tags')?.value || '';
            const tags = tagsInput.split(',').map(t => t.trim()).filter(t => t);
            formData.append('tags', JSON.stringify(tags));

            const response = await fetch('/api/chatterbox/save', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to save voice');
            }

            const result = await response.json();
            this.showStatus(`Voice "${voiceName}" saved successfully!`, 'success');

            // Close modal and clear form
            const modal = document.getElementById('save-voice-modal');
            if (modal) modal.style.display = 'none';
            document.getElementById('voice-name').value = '';
            document.getElementById('voice-description').value = '';
            document.getElementById('voice-tags').value = '';

            // Reload voices
            await this.loadVoices();
        } catch (error) {
            this.showStatus('Error: ' + error.message, 'error');
            console.error('Save voice error:', error);
        } finally {
            this.showLoading(false);
        }
    }

    async deleteClonedVoice(voiceId) {
        if (!confirm('Are you sure you want to delete this cloned voice?')) {
            return;
        }
        
        this.showLoading(true);
        
        try {
            const response = await fetch(`/api/chatterbox/voices/${voiceId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete voice');
            }
            
            this.showStatus('Voice deleted successfully', 'success');
            await this.loadVoices();
        } catch (error) {
            this.showStatus('Error: ' + error.message, 'error');
            console.error('Delete voice error:', error);
        } finally {
            this.showLoading(false);
        }
    }
}

// Initialize the app when DOM is loaded
let ttsApp;
document.addEventListener('DOMContentLoaded', () => {
    ttsApp = new TTSApp();
});

// Handle page visibility change to pause audio when tab is hidden
document.addEventListener('visibilitychange', () => {
    const audioPlayer = document.getElementById('audio-player');
    if (document.hidden && !audioPlayer.paused) {
        audioPlayer.pause();
    }
});

// Handle beforeunload to clean up audio URLs
window.addEventListener('beforeunload', () => {
    const audioPlayer = document.getElementById('audio-player');
    if (audioPlayer.src && audioPlayer.src.startsWith('blob:')) {
        URL.revokeObjectURL(audioPlayer.src);
    }
});
