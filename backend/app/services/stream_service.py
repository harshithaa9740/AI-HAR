"""
Modular Local IP Video Streaming Service (SIH Payload Camera Destination Streamer)
"""
import socket
import threading
import time
from typing import Dict, Any, Optional
import cv2
import numpy as np
from app.core.config import settings
from app.core.logging import logger
from app.services.video_service import video_service


class LocalIPStreamService:
    """
    Modular Offline IP Video Streamer.
    Streams compressed JPEG frames via UDP datagrams to a designated local IP/Port.
    """

    def __init__(self):
        self.enabled = settings.STREAM_ENABLED
        self.destination_ip = settings.STREAM_DESTINATION_IP
        self.port = settings.STREAM_PORT
        self.is_streaming = False
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.packets_sent = 0

    def start_streaming(self, destination_ip: Optional[str] = None, port: Optional[int] = None):
        if destination_ip:
            self.destination_ip = destination_ip
        if port:
            self.port = port

        if self.is_streaming:
            logger.info("IP Streaming is already active.")
            return

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._stop_event.clear()
            self.is_streaming = True
            self.packets_sent = 0
            self._thread = threading.Thread(target=self._stream_loop, daemon=True)
            self._thread.start()
            logger.info(f"Local IP Video Stream started -> {self.destination_ip}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start IP video stream: {e}")
            self.is_streaming = False

    def _stream_loop(self):
        while not self._stop_event.is_set() and self.is_streaming:
            frame = video_service.get_latest_frame()
            if frame is not None and self._sock:
                try:
                    # Compress frame to JPEG
                    ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    if ret:
                        data = buffer.tobytes()
                        # Limit packet size for standard UDP MTU or chunk
                        if len(data) < 65000:
                            self._sock.sendto(data, (self.destination_ip, self.port))
                            self.packets_sent += 1
                except Exception as e:
                    logger.debug(f"Streaming packet error: {e}")
            time.sleep(0.04)  # ~25 fps

    def stop_streaming(self):
        self.is_streaming = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._sock:
            self._sock.close()
            self._sock = None
        logger.info("Local IP Video Stream stopped.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_streaming": self.is_streaming,
            "destination_ip": self.destination_ip,
            "port": self.port,
            "packets_sent": self.packets_sent,
            "protocol": "UDP/MJPEG"
        }


stream_service = LocalIPStreamService()
