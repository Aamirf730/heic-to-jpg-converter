// Global state
let files = [];
let isConverting = false;

// DOM elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const fileListContainer = document.getElementById('fileListContainer');
const dropZoneContainer = document.getElementById('dropZoneContainer');
const headerActions = document.getElementById('headerActions');
const clearAllBtn = document.getElementById('clearAllBtn');
const downloadAllBtn = document.getElementById('downloadAllBtn');
const errorDisplay = document.getElementById('errorDisplay');
const errorMessage = document.getElementById('errorMessage');
const closeError = document.getElementById('closeError');
const fileCount = document.getElementById('fileCount');
const outputFormat = document.getElementById('outputFormat');
const stripExif = document.getElementById('stripExif');
const toggleSwitch = document.getElementById('toggleSwitch');
const toggleThumb = document.getElementById('toggleThumb');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    updateUI();
});

function initializeEventListeners() {
    // File input change
    fileInput.addEventListener('change', handleFileSelect);
    
    // Drag and drop events
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);
    dropZone.addEventListener('click', () => fileInput.click());
    
    // Settings
    outputFormat.addEventListener('change', updateUI);
    stripExif.addEventListener('change', updateUI);
    toggleSwitch.addEventListener('click', toggleStripExif);
    
    // Buttons
    clearAllBtn.addEventListener('click', clearAllFiles);
    downloadAllBtn.addEventListener('click', downloadAllFiles);
    closeError.addEventListener('click', hideError);
    
    // Keyboard navigation
    dropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });
}

function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
    dropZone.classList.add('scale-105');
}

function handleDragLeave(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    dropZone.classList.remove('scale-105');
}

function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    dropZone.classList.remove('scale-105');
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFiles(droppedFiles);
}

function handleFileSelect(e) {
    const selectedFiles = Array.from(e.target.files);
    handleFiles(selectedFiles);
    // Reset input to allow selecting the same file again
    e.target.value = '';
}

function handleFiles(fileList) {
    const validFiles = validateFiles(fileList);
    if (validFiles.length > 0) {
        uploadFiles(validFiles);
    }
}

function validateFiles(fileList) {
    const validFiles = [];
    const errors = [];
    
    fileList.forEach(file => {
        // Check file type
        const isValidType = file.name.toLowerCase().match(/\.(heic|heif)$/);
        if (!isValidType) {
            errors.push(`${file.name} is not a valid HEIC/HEIF file`);
            return;
        }
        
        // Check file size (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
            errors.push(`${file.name} is too large (max 10MB)`);
            return;
        }
        
        validFiles.push(file);
    });
    
    if (errors.length > 0) {
        showError(errors.join(', '));
        return [];
    }
    
    return validFiles;
}

async function uploadFiles(fileList) {
    isConverting = true;
    updateUI();
    
    for (const file of fileList) {
        const fileData = {
            id: `file-${Date.now()}-${Math.random()}`,
            file: file,
            fileName: file.name,
            status: 'pending',
            progress: 0
        };
        
        files.push(fileData);
        updateUI();
        
        try {
            // Upload file
            const formData = new FormData();
            formData.append('file', file);
            
            const uploadResponse = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!uploadResponse.ok) {
                throw new Error('Upload failed');
            }
            
            const uploadResult = await uploadResponse.json();
            fileData.sessionId = uploadResult.session_id;
            fileData.status = 'uploaded';
            fileData.progress = 10;
            updateUI();
            
            // Convert file
            await convertFile(fileData);
            
        } catch (error) {
            fileData.status = 'error';
            fileData.error = error.message;
            updateUI();
            showError(`Failed to process ${file.name}: ${error.message}`);
        }
    }
    
    isConverting = false;
    updateUI();
}

async function convertFile(fileData) {
    try {
        fileData.status = 'converting';
        fileData.progress = 20;
        updateUI();
        
        const convertData = {
            session_id: fileData.sessionId,
            strip_exif: stripExif.checked,
            output_format: outputFormat.value
        };
        
        const convertResponse = await fetch('/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(convertData)
        });
        
        if (!convertResponse.ok) {
            throw new Error('Conversion failed');
        }
        
        const convertResult = await convertResponse.json();
        fileData.status = 'completed';
        fileData.progress = 100;
        fileData.outputFormat = convertResult.output_format;
        updateUI();
        
    } catch (error) {
        fileData.status = 'error';
        fileData.error = error.message;
        updateUI();
    }
}

function downloadFile(fileData) {
    if (fileData.status !== 'completed') {
        return;
    }
    
    const downloadUrl = `/download/${fileData.sessionId}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = getOutputFileName(fileData.fileName, fileData.outputFormat);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function downloadAllFiles() {
    const completedFiles = files.filter(f => f.status === 'completed');
    
    if (completedFiles.length === 0) {
        return;
    }
    
    if (completedFiles.length === 1) {
        downloadFile(completedFiles[0]);
        return;
    }
    
    // For multiple files, download them one by one
    completedFiles.forEach(file => {
        setTimeout(() => downloadFile(file), 100);
    });
}

function clearAllFiles() {
    // Clear sessions on server
    files.forEach(file => {
        if (file.sessionId) {
            fetch(`/clear/${file.sessionId}`, { method: 'DELETE' }).catch(() => {});
        }
    });
    
    files = [];
    updateUI();
}

function toggleStripExif() {
    stripExif.checked = !stripExif.checked;
    updateToggleUI();
}

function updateToggleUI() {
    if (stripExif.checked) {
        toggleSwitch.classList.remove('bg-gray-300');
        toggleSwitch.classList.add('bg-red-500');
        toggleThumb.classList.remove('translate-x-0.5');
        toggleThumb.classList.add('translate-x-5');
    } else {
        toggleSwitch.classList.remove('bg-red-500');
        toggleSwitch.classList.add('bg-gray-300');
        toggleThumb.classList.remove('translate-x-5');
        toggleThumb.classList.add('translate-x-0.5');
    }
}

function updateUI() {
    updateFileList();
    updateHeaderActions();
    updateDropZone();
    updateToggleUI();
}

function updateFileList() {
    if (files.length === 0) {
        fileListContainer.style.display = 'none';
        dropZoneContainer.style.display = 'flex';
        return;
    }
    
    fileListContainer.style.display = 'flex';
    dropZoneContainer.style.display = 'none';
    
    fileCount.textContent = files.length;
    
    fileList.innerHTML = '';
    files.forEach(file => {
        const fileElement = createFileElement(file);
        fileList.appendChild(fileElement);
    });
}

function createFileElement(fileData) {
    const fileDiv = document.createElement('div');
    fileDiv.className = 'flex items-center justify-between p-4 bg-white rounded-xl shadow-sm border border-gray-100';
    
    const statusText = {
        'pending': '⏳ Waiting to convert...',
        'uploaded': '📤 Uploaded, converting...',
        'converting': '🔄 Converting...',
        'completed': '✅ Ready for download',
        'error': `❌ Error: ${fileData.error || 'Unknown error'}`
    };
    
    const statusClass = {
        'pending': 'text-gray-500',
        'uploaded': 'text-blue-500',
        'converting': 'text-yellow-500',
        'completed': 'text-green-500',
        'error': 'text-red-500'
    };
    
    fileDiv.innerHTML = `
        <div class="flex-1 min-w-0">
            <div class="flex items-center">
                <div class="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center mr-3">
                    <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                </div>
                <div>
                    <p class="font-medium text-gray-900 truncate">${fileData.fileName}</p>
                    <p class="text-sm ${statusClass[fileData.status]}">
                        ${statusText[fileData.status]}
                    </p>
                </div>
            </div>
        </div>
        
        <div class="flex items-center space-x-3">
            ${fileData.status === 'converting' ? `
                <div class="w-32">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${fileData.progress}%"></div>
                    </div>
                </div>
            ` : ''}
            
            ${fileData.status === 'completed' ? `
                <button class="download-btn px-3 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-all duration-200">
                    Download
                </button>
            ` : ''}
            
            ${fileData.status === 'error' ? `
                <span class="px-3 py-1 text-sm font-medium text-red-600 bg-red-50 rounded-lg">Failed</span>
            ` : ''}
        </div>
    `;
    
    // Add download button event listener
    const downloadBtn = fileDiv.querySelector('.download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => downloadFile(fileData));
    }
    
    return fileDiv;
}

function updateHeaderActions() {
    const completedFiles = files.filter(f => f.status === 'completed');
    const hasFiles = files.length > 0;
    
    if (hasFiles) {
        headerActions.style.display = 'flex';
        downloadAllBtn.textContent = completedFiles.length > 1 ? `Download All (${completedFiles.length})` : 'Download File';
        downloadAllBtn.disabled = completedFiles.length === 0 || isConverting;
        clearAllBtn.disabled = isConverting;
    } else {
        headerActions.style.display = 'none';
    }
}

function updateDropZone() {
    const isDisabled = isConverting;
    
    if (isDisabled) {
        dropZone.classList.add('opacity-50', 'cursor-not-allowed');
        dropZone.classList.remove('cursor-pointer');
    } else {
        dropZone.classList.remove('opacity-50', 'cursor-not-allowed');
        dropZone.classList.add('cursor-pointer');
    }
    
    // Update settings
    outputFormat.disabled = isDisabled;
    stripExif.disabled = isDisabled;
    toggleSwitch.classList.toggle('cursor-not-allowed', isDisabled);
}

function getOutputFileName(originalName, outputFormat) {
    const baseName = originalName.replace(/\.(heic|heif)$/i, '');
    const extension = outputFormat === 'jpeg' ? 'jpg' : outputFormat;
    return `${baseName}.${extension}`;
}

function showError(message) {
    errorMessage.textContent = message;
    errorDisplay.style.display = 'block';
}

function hideError() {
    errorDisplay.style.display = 'none';
}

// SEO Content Toggle
function initializeSEOToggle() {
    const seoToggle = document.getElementById('seoToggle');
    const seoContentInner = document.getElementById('seoContentInner');
    const seoIcon = document.getElementById('seoIcon');
    
    if (seoToggle && seoContentInner && seoIcon) {
        seoToggle.addEventListener('click', function() {
            const isVisible = seoContentInner.style.display !== 'none';
            
            if (isVisible) {
                seoContentInner.style.display = 'none';
                seoIcon.style.transform = 'rotate(0deg)';
            } else {
                seoContentInner.style.display = 'block';
                seoIcon.style.transform = 'rotate(180deg)';
            }
        });
    }
}

// Initialize SEO toggle when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeSEOToggle();
}); 