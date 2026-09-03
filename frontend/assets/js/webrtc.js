/**
 * AcademiQ — WebRTC Real-Time Signaling & PeerConnection Manager
 */

class WebRTCClient {
  constructor(roomId, peerId, isHost = false, onRemoteTrack = null, onPeerEvent = null) {
    this.roomId = roomId;
    this.peerId = peerId || `peer_${Math.random().toString(36).substring(2, 9)}`;
    this.isHost = isHost;
    this.onRemoteTrack = onRemoteTrack;
    this.onPeerEvent = onPeerEvent;

    this.localStream = null;
    this.peerConnections = {}; // target_peer_id -> RTCPeerConnection
    this.ws = null;
    this.iceServers = [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ];
  }

  async initialize(mediaConstraints = { video: true, audio: true }) {
    try {
      if (mediaConstraints.video || mediaConstraints.audio) {
        this.localStream = await navigator.mediaDevices.getUserMedia(mediaConstraints);
      }
      this.connectSignaling();
    } catch (err) {
      console.warn('[WebRTC] Media access restricted or unavailable:', err);
      // Still connect signaling for text chat
      this.connectSignaling();
    }
  }

  connectSignaling() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.WS_HOST || 'localhost:8000';
    const wsUrl = `${protocol}//${host}/api/v1/live/ws/${this.roomId}?peer_id=${this.peerId}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log(`[WebRTC] Connected to live signaling room ${this.roomId}`);
      if (this.onPeerEvent) this.onPeerEvent('connected', { peerId: this.peerId });
    };

    this.ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        await this.handleSignalMessage(msg);
      } catch (e) {
        console.error('[WebRTC] Signal parsing error:', e);
      }
    };

    this.ws.onclose = () => {
      console.log('[WebRTC] Disconnected from signaling server');
      if (this.onPeerEvent) this.onPeerEvent('disconnected', {});
    };
  }

  async handleSignalMessage(msg) {
    const sender = msg.sender_peer_id;

    if (msg.type === 'peer_joined') {
      console.log(`[WebRTC] New peer joined: ${msg.peer_id}`);
      if (this.isHost && msg.peer_id !== this.peerId) {
        // Educator initiates offer to the new student
        await this.createPeerConnection(msg.peer_id, true);
      }
      if (this.onPeerEvent) this.onPeerEvent('peer_joined', msg);
    } else if (msg.type === 'offer') {
      const pc = await this.createPeerConnection(sender, false);
      await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      this.sendSignal({
        type: 'answer',
        sdp: answer,
        target_peer_id: sender
      });
    } else if (msg.type === 'answer') {
      const pc = this.peerConnections[sender];
      if (pc) {
        await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
      }
    } else if (msg.type === 'ice_candidate') {
      const pc = this.peerConnections[sender];
      if (pc && msg.candidate) {
        await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
      }
    } else if (msg.type === 'chat') {
      if (this.onPeerEvent) this.onPeerEvent('chat', msg);
    } else if (msg.type === 'peer_left') {
      this.closePeer(msg.peer_id);
      if (this.onPeerEvent) this.onPeerEvent('peer_left', msg);
    }
  }

  async createPeerConnection(targetPeerId, isInitiator) {
    if (this.peerConnections[targetPeerId]) {
      return this.peerConnections[targetPeerId];
    }

    const pc = new RTCPeerConnection({ iceServers: this.iceServers });
    this.peerConnections[targetPeerId] = pc;

    // Attach local tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => pc.addTrack(track, this.localStream));
    }

    // Remote track listener
    pc.ontrack = (event) => {
      console.log(`[WebRTC] Received remote track from ${targetPeerId}`);
      if (this.onRemoteTrack) {
        this.onRemoteTrack(targetPeerId, event.streams[0]);
      }
    };

    // ICE Candidate handler
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignal({
          type: 'ice_candidate',
          candidate: event.candidate,
          target_peer_id: targetPeerId
        });
      }
    };

    if (isInitiator) {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      this.sendSignal({
        type: 'offer',
        sdp: offer,
        target_peer_id: targetPeerId
      });
    }

    return pc;
  }

  sendSignal(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendChatMessage(text, senderName) {
    this.sendSignal({
      type: 'chat',
      text: text,
      sender_name: senderName || 'Anonymous',
      timestamp: Date.now()
    });
  }

  closePeer(peerId) {
    if (this.peerConnections[peerId]) {
      this.peerConnections[peerId].close();
      delete this.peerConnections[peerId];
    }
  }

  disconnect() {
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
    }
    Object.keys(this.peerConnections).forEach(pid => this.closePeer(pid));
    if (this.ws) {
      this.ws.close();
    }
  }
}
