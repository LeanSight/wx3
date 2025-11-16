"""
Tests para el módulo sentence_grouping.py

Siguiendo TDD estricto: Red -> Green -> Refactor
"""

import pytest
from sentence_grouping import (
    is_sentence_end,
    is_strong_pause,
    group_chunks_by_sentences,
    group_chunks_by_speaker_only
)


class TestSentenceDetection:
    """Tests para detección de fin de oración y pausas."""
    
    def test_is_sentence_end_with_period(self):
        """RED: Detecta punto como fin de oración."""
        assert is_sentence_end("Hola mundo.")
    
    def test_is_sentence_end_with_question_mark(self):
        """RED: Detecta signo de interrogación."""
        assert is_sentence_end("¿Cómo estás?")
    
    def test_is_sentence_end_with_exclamation(self):
        """RED: Detecta signo de exclamación."""
        assert is_sentence_end("¡Qué bien!")
    
    def test_is_sentence_end_with_semicolon(self):
        """RED: Detecta punto y coma."""
        assert is_sentence_end("Primera parte; segunda parte;")
    
    def test_is_sentence_end_with_quotes(self):
        """RED: Detecta fin de oración con comillas."""
        assert is_sentence_end('Dijo "hola".')
    
    def test_is_sentence_end_with_parenthesis(self):
        """RED: Detecta fin de oración con paréntesis."""
        assert is_sentence_end("Texto (nota).")
    
    def test_is_not_sentence_end_with_comma(self):
        """RED: No detecta coma como fin de oración."""
        assert not is_sentence_end("Hola, mundo")
    
    def test_is_not_sentence_end_plain_text(self):
        """RED: No detecta texto plano como fin de oración."""
        assert not is_sentence_end("Hola mundo")
    
    def test_is_strong_pause_with_comma(self):
        """RED: Detecta coma como pausa fuerte."""
        assert is_strong_pause("Hola,")
    
    def test_is_strong_pause_with_colon(self):
        """RED: Detecta dos puntos como pausa fuerte."""
        assert is_strong_pause("Lista:")
    
    def test_is_not_strong_pause_plain_text(self):
        """RED: No detecta texto plano como pausa fuerte."""
        assert not is_strong_pause("Hola mundo")


class TestGroupChunksBySentences:
    """Tests para agrupación de chunks por oraciones."""
    
    def test_empty_chunks_returns_empty_list(self):
        """RED: Lista vacía retorna lista vacía."""
        result = group_chunks_by_sentences([])
        assert result == []
    
    def test_chunks_with_list_timestamps(self):
        """RED: Chunks con timestamps como listas (JSON format) se procesan correctamente."""
        chunks = [
            {
                'text': 'Primera oración.',
                'timestamp': [0.0, 2.0],  # Lista en lugar de tupla
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Segunda oración.',
                'timestamp': [2.0, 4.0],  # Lista en lugar de tupla
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 2
        assert result[0]['text'] == 'Primera oración.'
        assert result[0]['timestamp'] == (0.0, 2.0)  # Debe convertirse a tupla
        assert result[1]['text'] == 'Segunda oración.'
    
    def test_chunks_with_mixed_timestamp_types(self):
        """RED: Mezcla de tuplas y listas se maneja correctamente."""
        chunks = [
            {
                'text': 'Con tupla',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'y lista.',
                'timestamp': [1.0, 2.0],
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Con tupla y lista.'
        assert result[0]['timestamp'] == (0.0, 2.0)
    
    def test_single_chunk_with_period(self):
        """RED: Un chunk con punto se convierte en un segmento."""
        chunks = [
            {
                'text': 'Hola mundo.',
                'timestamp': (0.0, 2.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Hola mundo.'
        assert result[0]['timestamp'] == (0.0, 2.0)
        assert result[0]['speaker'] == 'SPEAKER_00'
    
    def test_two_chunks_same_sentence(self):
        """RED: Dos chunks sin punto final se agrupan."""
        chunks = [
            {
                'text': 'Hola',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'mundo.',
                'timestamp': (1.0, 2.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Hola mundo.'
        assert result[0]['timestamp'] == (0.0, 2.0)
    
    def test_two_complete_sentences(self):
        """RED: Dos oraciones completas generan dos segmentos."""
        chunks = [
            {
                'text': 'Primera oración.',
                'timestamp': (0.0, 2.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Segunda oración.',
                'timestamp': (2.0, 4.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 2
        assert result[0]['text'] == 'Primera oración.'
        assert result[1]['text'] == 'Segunda oración.'
    
    def test_speaker_change_creates_new_segment(self):
        """RED: Cambio de speaker crea nuevo segmento."""
        chunks = [
            {
                'text': 'Hola',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'mundo',
                'timestamp': (1.0, 2.0),
                'speaker': 'SPEAKER_01'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 2
        assert result[0]['speaker'] == 'SPEAKER_00'
        assert result[1]['speaker'] == 'SPEAKER_01'
    
    def test_max_chars_limit_with_comma(self):
        """RED: Exceder max_chars con coma crea nuevo segmento."""
        long_text = "A" * 50
        chunks = [
            {
                'text': long_text + ',',
                'timestamp': (0.0, 5.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': long_text,
                'timestamp': (5.0, 10.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks, max_chars=80)
        
        assert len(result) == 2
    
    def test_max_duration_limit_with_comma(self):
        """RED: Exceder max_duration con coma crea nuevo segmento."""
        chunks = [
            {
                'text': 'Texto largo,',
                'timestamp': (0.0, 8.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'más texto',
                'timestamp': (8.0, 16.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks, max_duration_s=10.0)
        
        assert len(result) == 2
    
    def test_absolute_max_chars_limit(self):
        """RED: Límite absoluto de caracteres fuerza segmentación."""
        very_long_text = "A" * 150
        chunks = [
            {
                'text': very_long_text,
                'timestamp': (0.0, 5.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Texto corto',
                'timestamp': (5.0, 7.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks, max_chars=80)
        
        assert len(result) == 2
    
    def test_absolute_max_duration_limit(self):
        """RED: Límite absoluto de duración fuerza segmentación."""
        chunks = [
            {
                'text': 'Texto muy largo',
                'timestamp': (0.0, 12.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Más texto',
                'timestamp': (12.0, 20.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks, max_duration_s=10.0)
        
        assert len(result) == 2
    
    def test_chunks_without_speaker(self):
        """RED: Chunks sin speaker se agrupan normalmente."""
        chunks = [
            {
                'text': 'Hola',
                'timestamp': (0.0, 1.0)
            },
            {
                'text': 'mundo.',
                'timestamp': (1.0, 2.0)
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Hola mundo.'
    
    def test_chunks_with_invalid_timestamp(self):
        """RED: Chunks con timestamp inválido se ignoran."""
        chunks = [
            {
                'text': 'Válido.',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Inválido',
                'timestamp': None,
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Otro válido.',
                'timestamp': (2.0, 3.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 2
        assert result[0]['text'] == 'Válido.'
        assert result[1]['text'] == 'Otro válido.'
    
    def test_chunks_with_empty_text(self):
        """RED: Chunks con texto vacío se ignoran."""
        chunks = [
            {
                'text': 'Hola',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': '   ',
                'timestamp': (1.0, 1.5),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'mundo.',
                'timestamp': (1.5, 2.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_sentences(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Hola mundo.'


class TestGroupChunksBySpeakerOnly:
    """Tests para agrupación de chunks solo por speaker."""
    
    def test_empty_chunks_returns_empty_list(self):
        """RED: Lista vacía retorna lista vacía."""
        result = group_chunks_by_speaker_only([])
        assert result == []
    
    def test_chunks_with_list_timestamps_speaker_only(self):
        """RED: Timestamps como listas funcionan en modo speaker-only."""
        chunks = [
            {
                'text': 'Speaker 0 parte 1.',
                'timestamp': [0.0, 2.0],
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Speaker 0 parte 2.',
                'timestamp': [2.0, 4.0],
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Speaker 1 habla.',
                'timestamp': [4.0, 6.0],
                'speaker': 'SPEAKER_01'
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 2
        assert result[0]['text'] == 'Speaker 0 parte 1. Speaker 0 parte 2.'
        assert result[0]['timestamp'] == (0.0, 4.0)
        assert result[1]['text'] == 'Speaker 1 habla.'
    
    def test_single_speaker_all_chunks_grouped(self):
        """RED: Un solo speaker agrupa todos los chunks."""
        chunks = [
            {
                'text': 'Primera parte.',
                'timestamp': (0.0, 2.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Segunda parte.',
                'timestamp': (2.0, 4.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Tercera parte.',
                'timestamp': (4.0, 6.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Primera parte. Segunda parte. Tercera parte.'
        assert result[0]['timestamp'] == (0.0, 6.0)
        assert result[0]['speaker'] == 'SPEAKER_00'
    
    def test_two_speakers_alternating(self):
        """RED: Dos speakers alternando crean múltiples segmentos."""
        chunks = [
            {
                'text': 'Speaker 0 habla.',
                'timestamp': (0.0, 2.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Speaker 1 responde.',
                'timestamp': (2.0, 4.0),
                'speaker': 'SPEAKER_01'
            },
            {
                'text': 'Speaker 0 continúa.',
                'timestamp': (4.0, 6.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 3
        assert result[0]['speaker'] == 'SPEAKER_00'
        assert result[1]['speaker'] == 'SPEAKER_01'
        assert result[2]['speaker'] == 'SPEAKER_00'
    
    def test_speaker_with_multiple_consecutive_chunks(self):
        """RED: Speaker con múltiples chunks consecutivos se agrupan."""
        chunks = [
            {
                'text': 'Parte 1',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Parte 2',
                'timestamp': (1.0, 2.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Parte 3',
                'timestamp': (2.0, 3.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Otro speaker',
                'timestamp': (3.0, 4.0),
                'speaker': 'SPEAKER_01'
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 2
        assert result[0]['text'] == 'Parte 1 Parte 2 Parte 3'
        assert result[0]['timestamp'] == (0.0, 3.0)
    
    def test_chunks_without_speaker_grouped_together(self):
        """RED: Chunks sin speaker se agrupan juntos."""
        chunks = [
            {
                'text': 'Sin speaker 1',
                'timestamp': (0.0, 1.0)
            },
            {
                'text': 'Sin speaker 2',
                'timestamp': (1.0, 2.0)
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Sin speaker 1 Sin speaker 2'
    
    def test_ignores_empty_text_chunks(self):
        """RED: Ignora chunks con texto vacío."""
        chunks = [
            {
                'text': 'Texto válido',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': '  ',
                'timestamp': (1.0, 1.5),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Más texto',
                'timestamp': (1.5, 2.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Texto válido Más texto'
    
    def test_ignores_invalid_timestamps(self):
        """RED: Ignora chunks con timestamps inválidos."""
        chunks = [
            {
                'text': 'Válido',
                'timestamp': (0.0, 1.0),
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Inválido',
                'timestamp': None,
                'speaker': 'SPEAKER_00'
            },
            {
                'text': 'Válido 2',
                'timestamp': (2.0, 3.0),
                'speaker': 'SPEAKER_00'
            }
        ]
        result = group_chunks_by_speaker_only(chunks)
        
        assert len(result) == 1
        assert result[0]['text'] == 'Válido Válido 2'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
