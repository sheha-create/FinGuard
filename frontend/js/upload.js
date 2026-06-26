class UploadManager {
    constructor() {
        this.dropZone = document.getElementById('drop-zone');
        this.fileInput = document.getElementById('file-input');
        this.progress = document.getElementById('upload-progress');
        this.progressFill = document.getElementById('progress-fill');
        this.progressText = document.getElementById('progress-text');
        this.result = document.getElementById('upload-result');

        this.init();
    }

    init() {
        this.dropZone.addEventListener('click', () => this.fileInput.click());

        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('drag-over');
        });

        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('drag-over');
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('drag-over');
            this.handleFile(e.dataTransfer.files[0]);
        });

        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFile(e.target.files[0]);
            }
        });
    }

    async handleFile(file) {
        if (!file) return;

        this.showProgress();
        this.result.classList.add('hidden');

        const formData = new FormData();
        formData.append('files', file);

        try {
            const response = await fetch('/upload/batch', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            this.showResult(data, file.name);

            if (window.app && (data.success || 0) > 0) {
                setTimeout(async () => {
                    await window.app.loadFullGraph();
                    await window.app.loadAccounts();
                    await window.app.updateStats();
                }, 300);
            }
        } catch (error) {
            this.showResult({ success: 0, errors: [`Upload failed: ${error.message}`] }, file.name);
        }

        this.fileInput.value = '';
    }

    showProgress() {
        this.progress.classList.remove('hidden');
        this.progressFill.style.width = '0%';
        this.progressText.textContent = 'Processing...';

        let width = 0;
        const interval = setInterval(() => {
            if (width >= 90) { clearInterval(interval); return; }
            width += 15;
            this.progressFill.style.width = width + '%';
        }, 100);
    }

    showResult(data, filename) {
        this.progress.classList.add('hidden');
        this.result.classList.remove('hidden');

        const success = data.success || 0;
        const total = data.total || data.total_transactions || 0;
        const alerts = data.alerts_generated || 0;
        const errors = data.errors || [];

        let html = '';

        if (success > 0) {
            html += `<div class="result-success">${success} transactions loaded from ${filename}</div>`;
            if (alerts > 0) {
                html += `<div class="result-alerts">${alerts} suspicious alerts generated</div>`;
            }
            html += '<div class="result-note">Graph updated with your data</div>';
        } else {
            html += `<div class="result-error">No transactions processed from ${filename}</div>`;
        }

        if (errors.length > 0) {
            html += '<div class="result-errors"><ul>';
            errors.slice(0, 5).forEach(err => html += `<li>${err}</li>`);
            if (errors.length > 5) html += `<li>+${errors.length - 5} more</li>`;
            html += '</ul></div>';
        }

        this.result.innerHTML = html;
    }
}

window.UploadManager = UploadManager;
