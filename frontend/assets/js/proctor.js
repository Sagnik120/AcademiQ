/**
 * AcademiQ — Real-Time ML Proctoring Client Engine
 * Handles webcam capture, frame dispatching, and live WebSocket trust score HUD.
 */

class ProctorManager {
  constructor(attemptId, videoElementId, trustScoreElementId) {
    this.attemptId = attemptId;
    this.videoEl = document.getElementById(videoElementId);
    this.trustScoreEl = document.getElementById(trustScoreElementId);
    
    this.mediaStream = null;
    this.captureInterval = null;
    this.ws = null;
    this.currentScore = 100.0;
    this.isSessionActive = false;

    // Create offscreen canvas for frame extraction
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
  }

  async start() {
    try {
      // 1. Initialize camera stream
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });

      if (this.videoEl) {
        this.videoEl.srcObject = this.mediaStream;
      }

      this.isSessionActive = true;

      // 2. Connect to real-time Proctor WebSocket
      this.connectWebSocket();

      // 3. Start frame capture loop (every 2.0 seconds)
      this.startCaptureLoop(2000);

      // 4. Attach window focus / tab switch listeners
      this.attachAntiCheatListeners();

      console.log(`[ProctorManager] Proctoring active for attempt ${this.attemptId}`);
    } catch (err) {
      console.error('[ProctorManager] Failed to start camera stream:', err);
      showToast('Camera access required for proctored examination', 'error');
    }
  }

  connectWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.WS_HOST || 'localhost:8000';
    const wsUrl = `${wsProtocol}//${wsHost}/api/v1/proctor/ws/${this.attemptId}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[ProctorManager] WebSocket connected to proctor engine');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.trust_score !== undefined) {
            this.updateTrustScore(parseFloat(data.trust_score));
          }
          if (data.alert_type) {
            this.handleProctorAlert(data);
          }
        } catch (e) {
          console.error('[ProctorManager] Error parsing WS message:', e);
        }
      };

      this.ws.onclose = () => {
        if (this.isSessionActive) {
          // Attempt reconnection after 3 seconds
          setTimeout(() => this.connectWebSocket(), 3000);
        }
      };
    } catch (e) {
      console.warn('[ProctorManager] WebSocket connection failed:', e);
    }
  }

  startCaptureLoop(intervalMs) {
    this.captureInterval = setInterval(() => {
      if (!this.isSessionActive || !this.videoEl || this.videoEl.readyState < 2) return;

      this.canvas.width = this.videoEl.videoWidth || 640;
      this.canvas.height = this.videoEl.videoHeight || 480;
      this.ctx.drawImage(this.videoEl, 0, 0, this.canvas.width, this.canvas.height);

      // Extract JPEG base64 (omitting the "data:image/jpeg;base64," prefix)
      const dataUrl = this.canvas.toDataURL('image/jpeg', 0.65);
      const base64Data = dataUrl.split(',')[1];

      this.sendFrame(base64Data);
    }, intervalMs);
  }

  async sendFrame(base64Frame) {
    try {
      const payload = {
        frame_base64: base64Frame,
        timestamp: Date.now() / 1000
      };

      // Dispatch to FastAPI proctoring frame ingestion
      const res = await api.post(`/proctor/sessions/${this.attemptId}/frame`, payload);
      if (res && res.current_trust_score !== undefined) {
        this.updateTrustScore(parseFloat(res.current_trust_score));
      }
    } catch (err) {
      // Non-blocking in case of temporary network drop
    }
  }

  updateTrustScore(score) {
    this.currentScore = Math.max(0, Math.min(100, Math.round(score * 10) / 10));

    if (this.trustScoreEl) {
      this.trustScoreEl.textContent = `${this.currentScore}%`;
      this.trustScoreEl.classList.remove('high', 'medium', 'low');

      if (this.currentScore >= 75) {
        this.trustScoreEl.classList.add('high');
      } else if (this.currentScore >= 50) {
        this.trustScoreEl.classList.add('medium');
      } else {
        this.trustScoreEl.classList.add('low');
      }
    }
  }

  handleProctorAlert(alertData) {
    const messages = {
      head_pose: 'Warning: Please keep your head facing forward towards the screen.',
      multiple_faces: 'Security Alert: Multiple individuals detected in your examination area!',
      face_absent: 'Warning: Candidate face not visible in camera frame.',
      mobile_device: 'Critical Alert: Prohibited electronic device detected!'
    };

    const alertMsg = messages[alertData.alert_type] || alertData.message || 'Suspicious activity detected';
    showToast(alertMsg, 'warning', 4000);
  }

  attachAntiCheatListeners() {
    // Tab visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && this.isSessionActive) {
        showToast('Warning: Leaving the exam tab is recorded as an integrity violation!', 'error');
        this.updateTrustScore(this.currentScore - 5.0);
      }
    });

    // Window blur
    window.addEventListener('blur', () => {
      if (this.isSessionActive) {
        showToast('Exam window focus lost.', 'warning');
      }
    });
  }

  stop() {
    this.isSessionActive = false;
    if (this.captureInterval) clearInterval(this.captureInterval);
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
    }
    if (this.ws) {
      this.ws.close();
    }
  }
}
