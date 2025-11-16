"""
Tests para output_convert.py con modos de agrupación.

Siguiendo TDD estricto: Red -> Green -> Refactor
"""

import pytest
import json
import tempfile
from pathlib import Path
from output_convert import convert_transcript


class TestOutputConvertWithGrouping:
    """Tests para output_convert con modos de agrupación."""
    
    def test_convert_with_sentences_mode_default(self):
        """RED: Conversión con modo sentences (por defecto)."""
        chunks = [
            {'text': 'Primera', 'timestamp': [0.0, 1.0], 'speaker': 'SPEAKER_00'},
            {'text': 'oración.', 'timestamp': [1.0, 2.0], 'speaker': 'SPEAKER_00'},
            {'text': 'Segunda oración.', 'timestamp': [2.0, 3.0], 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear JSON de entrada
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            # Convertir (modo sentences por defecto)
            output_file = convert_transcript(
                input_file=input_file,
                output_format='srt',
                output_dir=tmpdir,
                long_segments=False
            )
            
            content = output_file.read_text()
            # Debe haber 2 subtítulos (agrupados por oraciones)
            assert content.count('-->') == 2
            assert 'Primera oración.' in content
            assert 'Segunda oración.' in content
    
    def test_convert_with_speaker_only_mode(self):
        """RED: Conversión con modo speaker-only (--long)."""
        chunks = [
            {'text': 'Hola.', 'timestamp': [0.0, 1.0], 'speaker': 'SPEAKER_00'},
            {'text': '¿Cómo estás?', 'timestamp': [1.0, 2.0], 'speaker': 'SPEAKER_00'},
            {'text': 'Bien.', 'timestamp': [2.0, 3.0], 'speaker': 'SPEAKER_01'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            # Convertir con modo speaker-only
            output_file = convert_transcript(
                input_file=input_file,
                output_format='srt',
                output_dir=tmpdir,
                long_segments=True
            )
            
            content = output_file.read_text()
            # Debe haber 2 subtítulos (uno por speaker)
            assert content.count('-->') == 2
            assert 'Hola. ¿Cómo estás?' in content
            assert 'Bien.' in content
    
    def test_convert_vtt_with_sentences_mode(self):
        """RED: Conversión a VTT con modo sentences."""
        chunks = [
            {'text': 'Primera', 'timestamp': [0.0, 1.0], 'speaker': 'SPEAKER_00'},
            {'text': 'oración.', 'timestamp': [1.0, 2.0], 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            output_file = convert_transcript(
                input_file=input_file,
                output_format='vtt',
                output_dir=tmpdir,
                long_segments=False
            )
            
            content = output_file.read_text()
            assert 'WEBVTT' in content
            assert content.count('-->') == 1
            assert 'Primera oración.' in content
    
    def test_convert_vtt_with_speaker_only_mode(self):
        """RED: Conversión a VTT con modo speaker-only."""
        chunks = [
            {'text': 'Speaker 0.', 'timestamp': [0.0, 1.0], 'speaker': 'SPEAKER_00'},
            {'text': 'Más texto.', 'timestamp': [1.0, 2.0], 'speaker': 'SPEAKER_00'},
            {'text': 'Speaker 1.', 'timestamp': [2.0, 3.0], 'speaker': 'SPEAKER_01'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            output_file = convert_transcript(
                input_file=input_file,
                output_format='vtt',
                output_dir=tmpdir,
                long_segments=True
            )
            
            content = output_file.read_text()
            assert 'WEBVTT' in content
            assert content.count('-->') == 2
            assert 'Speaker 0. Más texto.' in content
    
    def test_convert_respects_max_chars(self):
        """RED: Conversión respeta max_chars en modo sentences."""
        long_text = "A" * 50
        chunks = [
            {'text': long_text + ',', 'timestamp': [0.0, 5.0], 'speaker': 'SPEAKER_00'},
            {'text': long_text, 'timestamp': [5.0, 10.0], 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            output_file = convert_transcript(
                input_file=input_file,
                output_format='srt',
                output_dir=tmpdir,
                long_segments=False,
                max_chars=80
            )
            
            content = output_file.read_text()
            # Debe crear 2 subtítulos porque excede max_chars
            assert content.count('-->') == 2
    
    def test_convert_respects_max_duration(self):
        """RED: Conversión respeta max_duration en modo sentences."""
        chunks = [
            {'text': 'Texto largo,', 'timestamp': [0.0, 8.0], 'speaker': 'SPEAKER_00'},
            {'text': 'más texto', 'timestamp': [8.0, 16.0], 'speaker': 'SPEAKER_00'}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.json"
            with open(input_file, 'w') as f:
                json.dump({'chunks': chunks, 'text': '', 'metrics': {}}, f)
            
            output_file = convert_transcript(
                input_file=input_file,
                output_format='srt',
                output_dir=tmpdir,
                long_segments=False,
                max_duration=10.0
            )
            
            content = output_file.read_text()
            # Debe crear 2 subtítulos porque excede max_duration
            assert content.count('-->') == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
