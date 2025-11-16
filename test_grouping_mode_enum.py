"""
Tests para verificar que GroupingMode enum se usa correctamente.

Siguiendo TDD estricto: Red -> Green -> Refactor
"""

import pytest
from constants import GroupingMode
from sentence_grouping import group_chunks_by_sentences, group_chunks_by_speaker_only
from output_formatters import save_subtitles
from output_convert import convert_transcript
import tempfile
import json
from pathlib import Path


class TestGroupingModeEnum:
    """Tests para verificar uso correcto del enum GroupingMode."""
    
    def test_grouping_mode_enum_has_correct_values(self):
        """RED: Enum tiene los valores correctos."""
        assert GroupingMode.sentences.value == "sentences"
        assert GroupingMode.speaker_only.value == "speaker-only"
    
    def test_save_subtitles_accepts_enum(self):
        """RED: save_subtitles acepta GroupingMode enum."""
        chunks = [
            {'text': 'Test.', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            
            # Debe aceptar enum directamente
            save_subtitles(
                transcription_result=None,
                output_file_path=output_path,
                format_type='srt',
                chunks=chunks,
                with_speaker=True,
                grouping_mode=GroupingMode.sentences  # Enum, no string
            )
            
            assert output_path.exists()
            content = output_path.read_text()
            assert 'Test.' in content
    
    def test_save_subtitles_accepts_enum_speaker_only(self):
        """RED: save_subtitles acepta GroupingMode.speaker_only."""
        chunks = [
            {'text': 'Test 1.', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'},
            {'text': 'Test 2.', 'timestamp': (1.0, 2.0), 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            
            save_subtitles(
                transcription_result=None,
                output_file_path=output_path,
                format_type='srt',
                chunks=chunks,
                with_speaker=True,
                grouping_mode=GroupingMode.speaker_only  # Enum
            )
            
            assert output_path.exists()
            content = output_path.read_text()
            # Debe agrupar ambos chunks
            assert 'Test 1. Test 2.' in content
    
    def test_convert_transcript_uses_enum_internally(self):
        """RED: convert_transcript usa enum internamente."""
        chunks = [
            {'text': 'Test.', 'timestamp': [0.0, 1.0], 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            # Internamente debe convertir bool a enum
            output_file = convert_transcript(
                input_file=input_file,
                output_format='srt',
                output_dir=tmpdir,
                long_segments=False  # Debe convertirse a GroupingMode.sentences
            )
            
            assert output_file.exists()
    
    def test_invalid_grouping_mode_string_raises_error(self):
        """RED: String inválido lanza error apropiado."""
        chunks = [
            {'text': 'Test.', 'timestamp': (0.0, 1.0), 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.srt"
            
            with pytest.raises(ValueError, match="Modo de agrupación inválido"):
                save_subtitles(
                    transcription_result=None,
                    output_file_path=output_path,
                    format_type='srt',
                    chunks=chunks,
                    with_speaker=True,
                    grouping_mode="invalid-mode"
                )
    
    def test_grouping_mode_enum_is_string_enum(self):
        """RED: GroupingMode es un str Enum (puede compararse con strings)."""
        # Esto permite compatibilidad con código existente
        assert GroupingMode.sentences == "sentences"
        assert GroupingMode.speaker_only == "speaker-only"
        
        # Y también funciona como enum
        assert isinstance(GroupingMode.sentences, GroupingMode)
        assert isinstance(GroupingMode.speaker_only, GroupingMode)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
