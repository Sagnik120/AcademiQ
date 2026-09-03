import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebRTCSignalingManager:
    """
    In-memory signaling server managing real-time peer-to-peer WebRTC connections,
    routing SDP offers, answers, ICE candidates, and chat messages between peers.
    """
    def __init__(self):
        # Maps room_id -> { peer_id: WebSocket }
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, peer_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {}

        # Notify existing room peers that a new peer joined
        for pid, conn in self.rooms[room_id].items():
            try:
                await conn.send_json({
                    "type": "peer_joined",
                    "peer_id": peer_id
                })
            except Exception:
                pass

        self.rooms[room_id][peer_id] = websocket
        logger.info("Peer %s joined WebRTC room %s (Total peers: %d)", peer_id, room_id, len(self.rooms[room_id]))

    async def disconnect(self, room_id: str, peer_id: str):
        if room_id in self.rooms and peer_id in self.rooms[room_id]:
            del self.rooms[room_id][peer_id]
            logger.info("Peer %s disconnected from room %s", peer_id, room_id)

            # Notify remaining peers
            for pid, conn in list(self.rooms[room_id].items()):
                try:
                    await conn.send_json({
                        "type": "peer_left",
                        "peer_id": peer_id
                    })
                except Exception:
                    pass

            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def forward_signal(self, room_id: str, sender_peer_id: str, message: dict):
        """
        Routes WebRTC message. If 'target_peer_id' is set, sends directly to that peer.
        Otherwise, broadcasts to all other peers in the room.
        """
        if room_id not in self.rooms:
            return

        target_id = message.get("target_peer_id")

        # 1. Targeted signaling (SDP offer, answer, or ICE candidate)
        if target_id and target_id in self.rooms[room_id]:
            target_conn = self.rooms[room_id][target_id]
            message["sender_peer_id"] = sender_peer_id
            try:
                await target_conn.send_json(message)
            except Exception as e:
                logger.error("Failed to route signal to %s: %s", target_id, e)
                await self.disconnect(room_id, target_id)
        else:
            # 2. Room broadcast (Chat messages, room announcements)
            message["sender_peer_id"] = sender_peer_id
            for pid, conn in list(self.rooms[room_id].items()):
                if pid != sender_peer_id:
                    try:
                        await conn.send_json(message)
                    except Exception:
                        await self.disconnect(room_id, pid)

signaling_manager = WebRTCSignalingManager()
