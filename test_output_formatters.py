"""
Tests para la integración de sentence_grouping con output_formatters.

Siguiendo TDD estricto: Red -> Green -> Refactor
"""

import pytest
from pathlib import Path
import tempfile
import os
from output_formatters import save_subtitles
from transcription import TranscriptionResult
from constants import GroupingMode


class MockTranscriptionResult:
    """Mock de TranscriptionResult para tests."""
    
    def __init__(self, chunks):
        self.chunks = chunks
        self.text = " ".join([c['text'] for c in chunks])
        self.audio_duration = 10.0
        self.processing_time = 1.0
        self.speed_factor = 10.0


class TestSaveSubtitlesWithGrouping:
    """Tests para save_subtitles con diferentes modos de agrupación."""
    
    def test_invalid_grouping_mode_raises_error(self):
        """RED: Modo de agrupación inválido lanza error."""
        chunks = [
            {'text': 'Primera parte', 'timestamp': (0.0, 2.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            with pytest.raises(ValueError, match="Modo de agrupación inválido"):
                save_subtitles(
                    result,
                    output_path,
                    "srt",
                    with_speaker=True,
                    grouping_mode="invalid"
                )
    
    def test_save_srt_with_sentence_grouping(self):
        """RED: Guardar SRT con agrupación por oraciones (modo 'sentences')."""
        chunks = [
            {'text': 'Primera parte', 'timestamp': (0.0, 2.0), 'speaker': 'SPEAKER_00'},
            {'text': 'de la oración.', 'timestamp': (2.0, 4.0), 'speaker': 'SPEAKER_00'},
            {'text': 'Segunda oración.', 'timestamp': (4.0, 6.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            save_subtitles(
                result,
                output_path,
                "srt",
                with_speaker=True,
                grouping_mode=GroupingMode.sentences
            )
            
            content = output_path.read_text()
            # Debe haber 2 subtítulos (agrupados por oraciones)
            assert content.count('-->') == 2
            assert 'Primera parte de la oración.' in content
            assert 'Segunda oración.' in content
    
    def test_save_srt_with_speaker_only_grouping(self):
        """RED: Guardar SRT con agrupación solo por speaker (modo 'speaker-only')."""
        chunks = [
            {'text': 'Hola.', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'},
            {'text': '¿Cómo estás?', 'timestamp': (1.0, 2.0), 'speaker': 'SPEAKER_00'},
            {'text': 'Bien, gracias.', 'timestamp': (2.0, 3.0), 'speaker': 'SPEAKER_01'},
            {'text': '¿Y tú?', 'timestamp': (3.0, 4.0), 'speaker': 'SPEAKER_01'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            save_subtitles(
                result,
                output_path,
                "srt",
                with_speaker=True,
                grouping_mode=GroupingMode.speaker_only
            )
            
            content = output_path.read_text()
            # Debe haber 2 subtítulos (uno por speaker)
            assert content.count('-->') == 2
            assert 'Hola. ¿Cómo estás?' in content
            assert 'Bien, gracias. ¿Y tú?' in content
    
    def test_save_vtt_with_sentence_grouping(self):
        """RED: Guardar VTT con agrupación por oraciones."""
        chunks = [
            {'text': 'Primera', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'},
            {'text': 'oración.', 'timestamp': (1.0, 2.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.vtt"
            save_subtitles(
                result,
                output_path,
                "vtt",
                with_speaker=True,
                grouping_mode=GroupingMode.sentences
            )
            
            content = output_path.read_text()
            assert 'WEBVTT' in content
            assert content.count('-->') == 1
            assert 'Primera oración.' in content
    
    def test_save_txt_with_sentence_grouping(self):
        """RED: Guardar TXT con agrupación por oraciones."""
        chunks = [
            {'text': 'Primera', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'},
            {'text': 'oración.', 'timestamp': (1.0, 2.0), 'speaker': 'SPEAKER_00'},
            {'text': 'Segunda oración.', 'timestamp': (2.0, 3.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.txt"
            save_subtitles(
                result,
                output_path,
                "txt",
                with_speaker=True,
                grouping_mode=GroupingMode.sentences
            )
            
            content = output_path.read_text()
            lines = content.strip().split('\n')
            # Debe haber 2 líneas (agrupadas por oraciones)
            assert len(lines) == 2
            assert 'SPEAKER_00: Primera oración.' in lines[0]
            assert 'SPEAKER_00: Segunda oración.' in lines[1]
    
    def test_grouping_respects_max_chars(self):
        """RED: La agrupación respeta el límite de caracteres."""
        long_text = "A" * 50
        chunks = [
            {'text': long_text + ',', 'timestamp': (0.0, 5.0), 'speaker': 'SPEAKER_00'},
            {'text': long_text, 'timestamp': (5.0, 10.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            save_subtitles(
                result,
                output_path,
                "srt",
                grouping_mode=GroupingMode.sentences,
                max_chars=80
            )
            
            content = output_path.read_text()
            # Debe crear 2 subtítulos porque excede max_chars
            assert content.count('-->') == 2
    
    def test_grouping_respects_max_duration(self):
        """RED: La agrupación respeta el límite de duración."""
        chunks = [
            {'text': 'Texto largo,', 'timestamp': (0.0, 8.0), 'speaker': 'SPEAKER_00'},
            {'text': 'más texto', 'timestamp': (8.0, 16.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            save_subtitles(
                result,
                output_path,
                "srt",
                grouping_mode=GroupingMode.sentences,
                max_duration_s=10.0
            )
            
            content = output_path.read_text()
            # Debe crear 2 subtítulos porque excede max_duration
            assert content.count('-->') == 2
    
    def test_default_grouping_mode_is_sentences(self):
        """RED: El modo de agrupación por defecto es 'sentences'."""
        chunks = [
            {'text': 'Primera', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'},
            {'text': 'oración.', 'timestamp': (1.0, 2.0), 'speaker': 'SPEAKER_00'}
        ]
        result = MockTranscriptionResult(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            # No especificar grouping_mode, debe usar 'sentences' por defecto
            save_subtitles(
                result,
                output_path,
                "srt",
                with_speaker=True
            )
            
            content = output_path.read_text()
            # Debe agrupar en una sola oración
            assert content.count('-->') == 1
            assert 'Primera oración.' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
