"""
Standardized Frame Data Model for AURAVISION Offline System
Transient in-memory representation of captured video frames for pipeline processing.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
import numpy as np


@dataclass
class Frame:
    """
    Standardized transient Frame model passed between ingestion, preprocessing,
    and future AI perception stages.
    
    IMPORTANT:
    Raw image arrays (`data`) are strictly transient and NEVER stored in the database.
    """
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    frame_index: int = 0
    width: int = 640
    height: int = 480
    source_id: str = "mock-camera"
    data: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_metadata_dict(self) -> Dict[str, Any]:
        """
        Return safe JSON-serializable dictionary of metadata without raw binary data.
        """
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "frame_index": self.frame_index,
            "width": self.width,
            "height": self.height,
            "source_id": self.source_id,
            "metadata": self.metadata
        }

    def __repr__(self) -> str:
        shape_info = f"{self.data.shape}" if self.data is not None else "None"
        return (
            f"Frame(id={self.frame_id[:8]}..., idx={self.frame_index}, "
            f"src={self.source_id}, {self.width}x{self.height}, data={shape_info})"
        )
