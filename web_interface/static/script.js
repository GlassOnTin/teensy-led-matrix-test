// LED Matrix Web Interface JavaScript

class LEDMatrixController {
    constructor() {
        this.baseUrl = '';
        this.selectedColor = 'white';
        this.websocket = null;
        this.retryCount = 0;
        this.maxRetries = 5;
        this.lastApiResponseTime = 0;
        this.startTime = Date.now();
        this.statusUpdateInterval = null;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadStatus();
        this.updateUI();
        this.startStatusUpdates();
    }

    setupEventListeners() {
        // Color selection
        document.querySelectorAll('.color-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const color = e.target.getAttribute('onclick').match(/'([^']+)'/)[1];
                this.selectColor(color);
            });
        });

        // Brightness slider
        const brightnessSlider = document.getElementById('brightness');
        brightnessSlider.addEventListener('input', (e) => {
            this.setBrightness(e.target.value);
        });

        // Form submission
        document.getElementById('message-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // Power button
        document.getElementById('power-btn').addEventListener('click', () => {
            this.togglePower();
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.retryCount = 0;
            this.showToast('Connected to LED Matrix', 'success');
            this.updateConnectionStatus(true);
            this.updateWebSocketStatus('Connected');
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            this.updateWebSocketStatus('Disconnected');

            // Retry connection
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                this.updateWebSocketStatus(`Reconnecting... (${this.retryCount}/${this.maxRetries})`);
                setTimeout(() => {
                    console.log(`Reconnecting... (${this.retryCount}/${this.maxRetries})`);
                    this.connectWebSocket();
                }, 2000 * this.retryCount);
            } else {
                this.updateWebSocketStatus('Connection failed');
            }
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'status':
                this.updateStatusDisplay(data.data);
                break;
            case 'power_changed':
                this.updatePowerButton(data.data.new);
                break;
            case 'brightness_changed':
                this.updateBrightnessDisplay(data.data.new);
                break;
            case 'mode_changed':
                this.updateModeDisplay(data.data.new);
                break;
            case 'text_changed':
                this.updateTextDisplay(data.data.new);
                break;
        }
    }

    async apiRequest(endpoint, method = 'GET', data = null) {
        const url = `${this.baseUrl}/api${endpoint}`;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const startTime = Date.now();

        try {
            const response = await fetch(url, options);

            this.lastApiResponseTime = Date.now() - startTime;
            this.updateApiResponseTime(this.lastApiResponseTime);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            this.showToast(`Error: ${error.message}`, 'error');
            this.updateApiResponseTime('Error');
            throw error;
        }
    }

    async loadStatus() {
        try {
            const status = await this.apiRequest('/status');
            this.updateStatusDisplay(status);
        } catch (error) {
            console.error('Failed to load status:', error);
        }
    }

    async sendMessage(event) {
        if (event) {
            event.preventDefault();
        }

        const message = document.getElementById('message').value.trim();
        if (!message) {
            this.showToast('Please enter a message', 'error');
            return false;
        }

        const requestData = {
            message: message,
            color: this.selectedColor,
            effect: document.getElementById('effect').value,
            font: document.getElementById('font').value,
            duration: 0,
            position: 'center'
        };

        try {
            this.setLoading(true);
            await this.apiRequest('/text', 'POST', requestData);
            this.showToast(`Message sent: "${message}"`, 'success');
            document.getElementById('message').value = '';
        } catch (error) {
            console.error('Failed to send message:', error);
        } finally {
            this.setLoading(false);
        }

        return false;
    }

    async sendPreset(presetName) {
        try {
            this.setLoading(true);
            await this.apiRequest(`/text/presets/${presetName}`, 'POST');
            this.showToast(`Preset activated: ${presetName}`, 'success');
        } catch (error) {
            console.error('Failed to send preset:', error);
        } finally {
            this.setLoading(false);
        }
    }

    selectColor(color) {
        // Remove previous selection
        document.querySelectorAll('.color-btn').forEach(btn => {
            btn.classList.remove('selected');
        });

        // Add selection to clicked button
        document.querySelector(`.color-btn.${color}`).classList.add('selected');

        this.selectedColor = color;
        document.getElementById('selected-color').value = color;
    }

    async setBrightness(value) {
        document.getElementById('brightness-value').textContent = value;
        document.getElementById('brightness-display').textContent = `Brightness: ${value}`;

        try {
            await this.apiRequest('/brightness', 'POST', { level: parseInt(value) });
        } catch (error) {
            console.error('Failed to set brightness:', error);
        }
    }

    async togglePower() {
        const powerBtn = document.getElementById('power-btn');
        const isOn = powerBtn.classList.contains('on');

        try {
            this.setLoading(true);
            await this.apiRequest('/power', 'POST', { state: !isOn });
            this.updatePowerButton(!isOn);
            this.showToast(`Display ${!isOn ? 'turned on' : 'turned off'}`, 'info');
        } catch (error) {
            console.error('Failed to toggle power:', error);
        } finally {
            this.setLoading(false);
        }
    }

    async switchToEffects() {
        try {
            this.setLoading(true);
            await this.apiRequest('/mode', 'POST', { mode: 'effects' });
            this.showToast('Switched to effects mode', 'info');
        } catch (error) {
            console.error('Failed to switch to effects:', error);
        } finally {
            this.setLoading(false);
        }
    }

    updateStatusDisplay(status) {
        document.getElementById('current-mode').textContent = status.mode;
        document.getElementById('active-effect').textContent = status.active_effect;

        if (status.text_state && status.text_state.message) {
            document.getElementById('last-message').textContent = status.text_state.message;
        }

        this.updatePowerButton(status.power);
        this.updateBrightnessDisplay(status.brightness);

        // Update status indicators
        this.updateStatusIndicator('mode-indicator', status.mode !== 'off');
        this.updateStatusIndicator('effect-indicator', status.active_effect !== 'none');
        this.updateStatusIndicator('connection-indicator', true);
        this.updateStatusIndicator('performance-indicator', true);
        this.updateStatusIndicator('hardware-indicator', status.device_connected !== false);

        // Update device-specific information
        if (status.device_connected !== undefined) {
            this.updateDeviceStatus(status.device_connected ? 'Connected' : 'Disconnected');
            document.getElementById('serial-status').textContent = status.device_connected ? 'Connected' : 'Disconnected';
        }

        if (status.device_lock !== undefined) {
            document.getElementById('device-lock-status').textContent = status.device_lock ? 'Locked' : 'Available';
        }

        // Update real metrics from API
        if (status.memory_usage_mb !== undefined) {
            document.getElementById('memory-usage').textContent = `${status.memory_usage_mb} MB`;
        }

        // Update frame rate from frame_stats if available
        if (status.frame_stats && status.frame_stats.fps) {
            document.getElementById('frame-rate').textContent = `${status.frame_stats.fps} fps`;
        } else {
            document.getElementById('frame-rate').textContent = '-- fps';
        }

        // Simulate some hardware metrics that aren't yet available from hardware
        document.getElementById('temperature').textContent = '42 °C';
        document.getElementById('power-draw').textContent = '12 W';
    }

    updatePowerButton(isOn) {
        const powerBtn = document.getElementById('power-btn');
        const icon = powerBtn.querySelector('.icon');
        const label = powerBtn.querySelector('.label');

        if (isOn) {
            powerBtn.classList.remove('off');
            powerBtn.classList.add('on');
            icon.textContent = '⚡';
            label.textContent = 'Power On';
        } else {
            powerBtn.classList.remove('on');
            powerBtn.classList.add('off');
            icon.textContent = '⏻';
            label.textContent = 'Power Off';
        }
    }

    updateBrightnessDisplay(brightness) {
        document.getElementById('brightness').value = brightness;
        document.getElementById('brightness-value').textContent = brightness;
        document.getElementById('brightness-display').textContent = `Brightness: ${brightness}`;
    }

    updateModeDisplay(mode) {
        document.getElementById('current-mode').textContent = mode;
    }

    updateTextDisplay(textState) {
        if (textState.message) {
            document.getElementById('last-message').textContent = textState.message;
        }
    }

    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('status');
        if (connected) {
            statusEl.textContent = 'Connected';
            statusEl.className = 'status online';
        } else {
            statusEl.textContent = 'Disconnected';
            statusEl.className = 'status offline';
        }
    }

    setLoading(loading) {
        const elements = document.querySelectorAll('button, input, select');
        elements.forEach(el => {
            if (loading) {
                el.classList.add('loading');
                el.disabled = true;
            } else {
                el.classList.remove('loading');
                el.disabled = false;
            }
        });
    }

    showToast(message, type = 'info') {
        // Remove existing toasts
        document.querySelectorAll('.toast').forEach(toast => toast.remove());

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        document.body.appendChild(toast);

        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);

        // Hide toast after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    updateUI() {
        // Initialize UI state
        this.selectColor('white');
        this.updateLastUpdateTime();
    }

    startStatusUpdates() {
        // Update every 5 seconds
        this.statusUpdateInterval = setInterval(() => {
            this.updateUptime();
            this.updateLastUpdateTime();

            // Periodically refresh status
            if (Date.now() % 30000 < 5000) { // Every 30 seconds
                this.loadStatus();
            }
        }, 5000);
    }

    updateWebSocketStatus(status) {
        const element = document.getElementById('websocket-status');
        if (element) {
            element.textContent = status;
        }
    }

    updateApiResponseTime(time) {
        const element = document.getElementById('api-response-time');
        if (element) {
            element.textContent = typeof time === 'number' ? `${time} ms` : time;
        }
    }

    updateUptime() {
        const element = document.getElementById('uptime');
        if (element) {
            const uptimeMs = Date.now() - this.startTime;
            const hours = Math.floor(uptimeMs / (1000 * 60 * 60));
            const minutes = Math.floor((uptimeMs % (1000 * 60 * 60)) / (1000 * 60));
            element.textContent = `${hours}h ${minutes}m`;
        }
    }

    updateLastUpdateTime() {
        const element = document.getElementById('last-update');
        if (element) {
            const now = new Date();
            element.textContent = `Last update: ${now.toLocaleTimeString()}`;
        }
    }

    updateStatusIndicator(elementId, isOnline, isWarning = false) {
        const element = document.getElementById(elementId);
        if (element) {
            element.className = 'status-indicator';
            if (isOnline) {
                element.classList.add('online');
            } else if (isWarning) {
                element.classList.add('warning');
            } else {
                element.classList.add('offline');
            }
        }
    }

    updateDeviceStatus(status) {
        const element = document.getElementById('device-status');
        if (element) {
            element.textContent = `Device: ${status}`;
            element.className = 'status';
            if (status.toLowerCase().includes('connected') || status.toLowerCase().includes('online')) {
                element.classList.add('online');
            } else {
                element.classList.add('offline');
            }
        }
    }
}

// Global functions for onclick handlers
function sendPreset(presetName) {
    window.ledController.sendPreset(presetName);
}

function selectColor(color) {
    window.ledController.selectColor(color);
}

function setBrightness(value) {
    window.ledController.setBrightness(value);
}

function togglePower() {
    window.ledController.togglePower();
}

function switchToEffects() {
    window.ledController.switchToEffects();
}

function sendMessage(event) {
    return window.ledController.sendMessage(event);
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.ledController = new LEDMatrixController();
});