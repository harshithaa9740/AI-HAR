"""
Offline Local Voice Alert Engine (Pluggable Local TTS and Mock Voice)
"""
import threading
import queue
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.logging import logger


class BaseVoiceEngine(ABC):
    @abstractmethod
    def speak(self, text: str):
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        pass


class MockVoiceEngine(BaseVoiceEngine):
    """Logs voice announcements locally and records speech queue."""

    def __init__(self):
        self.spoken_history: List[str] = []

    def speak(self, text: str):
        self.spoken_history.append(text)
        logger.info(f"[VOICE ANNOUNCEMENT]: \"{text}\"")

    def get_status(self) -> Dict[str, Any]:
        return {
            "engine": "MockVoiceEngine",
            "type": "MOCK",
            "enabled": True,
            "spoken_count": len(self.spoken_history),
            "last_spoken": self.spoken_history[-1] if self.spoken_history else None
        }


class LocalTTSEngine(BaseVoiceEngine):
    """
    Offline Local Text-to-Speech Engine using pyttsx3 / Windows SAPI / Linux eSpeak.
    Runs asynchronously in a background worker thread to prevent blocking FastAPI request threads.
    """

    def __init__(self):
        self._speech_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_available = False
        self.spoken_history: List[str] = []
        self._initialize()

    def _initialize(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.stop()
            self._is_available = True
            self._start_worker()
            logger.info("Offline Local TTS initialized successfully.")
        except Exception as e:
            logger.warning(f"Local TTS initialization failed: {e}. Falling back to Mock Voice.")
            self._is_available = False

    def _start_worker(self):
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()

    def _run_loop(self):
        import pyttsx3
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            while not self._stop_event.is_set():
                try:
                    text = self._speech_queue.get(timeout=0.5)
                    if text:
                        engine.say(text)
                        engine.runAndWait()
                        self.spoken_history.append(text)
                    self._speech_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"TTS Worker error: {e}")
        except Exception as e:
            logger.error(f"TTS loop failed: {e}")

    def speak(self, text: str):
        if self._is_available:
            self._speech_queue.put(text)
            logger.info(f"[VOICE QUEUED]: \"{text}\"")
        else:
            logger.info(f"[VOICE SIMULATED]: \"{text}\"")
            self.spoken_history.append(text)

    def get_status(self) -> Dict[str, Any]:
        return {
            "engine": "LocalTTSEngine",
            "type": "LOCAL_TTS" if self._is_available else "FALLBACK_MOCK",
            "is_available": self._is_available,
            "spoken_count": len(self.spoken_history)
        }


# Global Voice Engine instance
def create_voice_engine() -> BaseVoiceEngine:
    if settings.VOICE_ENABLED and settings.VOICE_ENGINE == "local_tts":
        return LocalTTSEngine()
    return MockVoiceEngine()


voice_engine = create_voice_engine()
