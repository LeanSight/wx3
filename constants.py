# constants.py
"""Centralized constants for the entire WX3 application."""

from enum import Enum
from typing import Dict, List, Optional

# Enumeration classes
class Task(str, Enum):
    """Tasks supported by transcription models."""
    transcribe = "transcribe"
    translate = "translate"

class Device(str, Enum):
    """Available devices for inference."""
    auto = "auto"
    cpu = "cpu"
    cuda = "cuda"
    mps = "mps"

class LogLevel(str, Enum):
    """Available logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class SubtitleFormat(str, Enum):
    """Supported formats for subtitles and transcriptions."""
    SRT = "srt"
    VTT = "vtt"
    TXT = "txt"
    JSON = "json"
    
    @classmethod
    def from_string(cls, value: str) -> 'SubtitleFormat':
        """Converts a string to subtitle format."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unsupported format: {value}")

# Transcription constants
DEFAULT_MODEL = "openai/whisper-large-v3"
DEFAULT_TASK = Task.transcribe
DEFAULT_LANGUAGE = None  # None for automatic detection
DEFAULT_CHUNK_LENGTH = 8
DEFAULT_BATCH_SIZE = 8
DEFAULT_ATTN_TYPE = "sdpa"

# Diarization constants
DEFAULT_DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"
DEFAULT_NUM_SPEAKERS = None  # None for automatic detection

# Output format constants
DEFAULT_FORMATS = {
    "transcribe": ["srt"],
    "diarize": ["json"],
    "process": ["srt"]
}

# Sentence grouping constants
class GroupingMode(str, Enum):
    """Modos de agrupación de subtítulos."""
    sentences = "sentences"
    speaker_only = "speaker-only"

DEFAULT_GROUPING_MODE = GroupingMode.sentences
DEFAULT_MAX_CHARS = 80
DEFAULT_MAX_DURATION_S = 10.0

# Logging constants
DEFAULT_LOG_LEVEL = LogLevel.INFO
DEFAULT_LOG_FORMAT = "%(message)s"
DEFAULT_LOG_DATE_FORMAT = "[%X]"

# Supported file extensions
AUDIO_EXTENSIONS = [".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a", ".aiff", ".wma"]
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".mpeg", ".mpg"]

# Common messages
MSG_NO_FILES_FOUND = "No valid files found."
MSG_PROCESSING_FILES = "Processing %s file(s)..."
MSG_PROCESSING_FILE = "[%s/%s] Processing: %s"
MSG_SAVING_RESULTS = "Saving results for: %s"
MSG_FILE_SAVED = "  %s saved: %s"
MSG_UNKNOWN_FORMAT = "Unknown format: %s"
MSG_ERROR_PROCESSING = "Error processing %s: %s"

# CLI help messages
HELP_APP = "WX3: CLI tool for audio/video transcription and diarization"
HELP_AUDIO_INPUTS = "Audio/video files to process"
HELP_MODEL = "Whisper model to use"
HELP_TASK = "Task to perform (transcribe or translate)"
HELP_LANG = "Language code (e.g.: en, es). None for automatic detection"
HELP_CHUNK_LENGTH = "Segment length in seconds"
HELP_BATCH_SIZE = "Batch size for processing"
HELP_ATTN_TYPE = "Attention type (sdpa, eager, flash)"
HELP_DEVICE = "Device for inference"
HELP_FORMATS = "Output formats"
HELP_LOG_LEVEL = "Logging level"
HELP_LOG_FILE = "File to save logs"
HELP_SHOW_FORMATS = "Show supported file formats"
HELP_HF_TOKEN = "Hugging Face access token"
HELP_NUM_SPEAKERS = "Number of speakers (optional)"
HELP_TRANSCRIBE = "Transcribe audio/video files"
HELP_DIARIZE = "Diarize audio/video files"
HELP_PROCESS = "Process audio/video files (transcription + diarization)"
HELP_LONG_SEGMENTS = "Create long segments (group only by speaker changes). Default: group by sentences with punctuation"
HELP_MAX_CHARS = "Maximum characters per subtitle segment (only for sentence grouping)"
HELP_MAX_DURATION = "Maximum duration in seconds per subtitle segment (only for sentence grouping)"

# Panel titles and content
PANEL_TITLE = "WX3 - Format Information"
PANEL_SUPPORTED_FORMATS = "Supported formats:"
PANEL_AUDIO_FORMATS = "Audio: %s"
PANEL_VIDEO_FORMATS = "Video: %s"

# Log messages
LOG_LOAD_TIMES_TITLE = "== Module loading times =="
LOG_LOAD_TIME_ENTRY = "%s: %.4fs"
LOG_INIT_TRANSCRIPTION = "Initializing transcription pipeline (model: %s, device: %s)"
LOG_INIT_DIARIZATION = "Initializing diarization pipeline (device: %s)"
LOG_INIT_PIPELINES = "Initializing pipelines (model: %s, device: %s)"
LOG_TRANSCRIBING = "Transcribing: %s"
LOG_DIARIZING = "Diarizing: %s"
LOG_TASK = "  Task: %s"
LOG_LANGUAGE = "  Language: %s"
LOG_SEGMENT_BATCH = "  Segment size: %ss, Batch: %s"
LOG_NUM_SPEAKERS = "  Number of speakers: %s"

# Function to get model kwargs based on attention type
def get_model_kwargs(attn_type: str) -> dict:
    """Generates model_kwargs according to the specified attention type."""
    if attn_type == "sdpa":
        return {"attn_implementation": "sdpa"}
    elif attn_type == "eager":
        return {"attn_implementation": "eager"}
    elif attn_type == "flash":
        return {"attn_implementation": "flash_attention_2"}
    return {}