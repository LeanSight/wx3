#!/usr/bin/env python3
"""
Script CLI para convertir transcripciones de AssemblyAI (JSON) a formato SRT.
Utiliza argparse para manejar parámetros de línea de comandos.
"""

import argparse
import json
import sys
from pathlib import Path
from assemblyai_json_to_srt import words_to_srt
from constants import GroupingMode


def load_json_file(filepath):
    """
    Carga y valida el archivo JSON de timestamps.
    
    Args:
        filepath: Ruta al archivo JSON
        
    Returns:
        Lista de palabras con timestamps
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        json.JSONDecodeError: Si el JSON es inválido
        ValueError: Si el formato de datos es incorrecto
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            words = json.load(f)
        
        # Validación básica
        if not isinstance(words, list):
            raise ValueError("El JSON debe contener una lista de palabras")
        
        if not words:
            raise ValueError("El JSON está vacío")
        
        # Validar que cada palabra tenga los campos necesarios
        required_fields = ['text', 'start', 'end', 'speaker']
        for i, word in enumerate(words[:5]):  # Validar las primeras 5
            missing = [f for f in required_fields if f not in word]
            if missing:
                raise ValueError(
                    f"Palabra {i+1} no tiene los campos requeridos: {missing}"
                )
        
        return words
    
    except FileNotFoundError:
        print(f"❌ Error: Archivo no encontrado: {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: JSON inválido: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def parse_speaker_mapping(mapping_str):
    """
    Parsea el string de mapeo de speakers.
    
    Args:
        mapping_str: String en formato "A=Nombre1,B=Nombre2"
        
    Returns:
        Diccionario de mapeo
        
    Example:
        "A=Marcel,B=Agustín" -> {'A': 'Marcel', 'B': 'Agustín'}
    """
    if not mapping_str:
        return {}
    
    mapping = {}
    try:
        for pair in mapping_str.split(','):
            pair = pair.strip()
            if '=' not in pair:
                continue
            key, value = pair.split('=', 1)
            mapping[key.strip()] = value.strip()
        return mapping
    except Exception as e:
        print(f"⚠️  Advertencia: Error parseando mapeo de speakers: {e}", 
              file=sys.stderr)
        return {}


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(
        description='Convierte transcripciones de AssemblyAI (JSON) a formato SRT con labels de speakers.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  %(prog)s input.json -o output.srt --type sub
  %(prog)s timestamps.json --type speaker --speakers "A=Marcel,B=Agustín"
  %(prog)s data.json -o subs.srt --type sub --max-chars 100 --max-duration 12000

Tipos de segmentación:
  sub      - Segmentación por oraciones completas (mejor para lectura)
  speaker  - Segmentación solo por cambio de speaker (menos segmentos)
        """
    )
    
    # Argumentos posicionales
    parser.add_argument(
        'input',
        type=str,
        help='Archivo JSON con timestamps de AssemblyAI'
    )
    
    # Argumentos opcionales
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Archivo SRT de salida (default: input_name.srt)'
    )
    
    parser.add_argument(
        '--type',
        type=str,
        choices=['sub', 'speaker'],
        default='sub',
        help='Tipo de segmentación: "sub" para oraciones, "speaker" para cambios de hablante (default: sub)'
    )
    
    parser.add_argument(
        '--speakers',
        type=str,
        default=None,
        help='Mapeo de speakers en formato "A=Nombre1,B=Nombre2" (ej: "A=Marcel,B=Agustín")'
    )
    
    parser.add_argument(
        '--max-chars',
        type=int,
        default=80,
        help='Máximo de caracteres por subtítulo (solo para --type sub) (default: 80)'
    )
    
    parser.add_argument(
        '--max-duration',
        type=int,
        default=10000,
        help='Máxima duración en ms por subtítulo (solo para --type sub) (default: 10000)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Mostrar información detallada del proceso'
    )
    
    # Parsear argumentos
    args = parser.parse_args()
    
    # Determinar nombre de archivo de salida
    if args.output is None:
        input_path = Path(args.input)
        args.output = input_path.stem + '.srt'
    
    # Banner
    if args.verbose:
        print("=" * 70)
        print("CONVERSIÓN DE ASSEMBLYAI JSON A SRT CON SPEAKER LABELS")
        print("=" * 70)
        print()
    
    # Cargar JSON
    print(f"📂 Cargando archivo: {args.input}")
    words = load_json_file(args.input)
    
    if args.verbose:
        print(f"   ✓ Total de palabras: {len(words):,}")
        
        # Estadísticas de speakers
        speakers = set(w['speaker'] for w in words)
        print(f"   ✓ Speakers detectados: {', '.join(sorted(speakers))}")
        print()
    
    # Parsear mapeo de speakers
    speaker_mapping = parse_speaker_mapping(args.speakers)
    if speaker_mapping and args.verbose:
        print("🎤 Mapeo de speakers:")
        for key, value in speaker_mapping.items():
            print(f"   {key} → {value}")
        print()
    
    # Determinar modo de conversión usando enum
    mode_map = {
        'sub': GroupingMode.sentences,
        'speaker': GroupingMode.speaker_only
    }
    mode = mode_map[args.type]
    
    # Información del proceso
    mode_description = {
        'sub': 'segmentación por oraciones completas',
        'speaker': 'segmentación solo por cambio de speaker'
    }
    
    print(f"📝 Convirtiendo con {mode_description[args.type]}...")
    
    if args.type == 'sub' and args.verbose:
        print(f"   • Máximo de caracteres: {args.max_chars}")
        print(f"   • Máxima duración: {args.max_duration} ms")
    
    # Convertir a SRT
    try:
        # Preparar kwargs según el tipo
        kwargs = {
            'words': words,
            'speaker_names': speaker_mapping,
            'output_file': args.output,
            'mode': mode
        }
        
        # Agregar parámetros de límites si es modo sentences
        if mode == GroupingMode.sentences:
            kwargs['max_chars'] = args.max_chars
            kwargs['max_duration_ms'] = args.max_duration
        
        srt_content = words_to_srt(**kwargs)
        
        # Contar segmentos
        num_segments = srt_content.count('-->')
        
        print(f"   ✓ Total de segmentos generados: {num_segments:,}")
        print()
        print(f"✅ Archivo SRT generado exitosamente: {args.output}")
        
        if args.verbose:
            # Calcular duración total
            total_duration_ms = words[-1]['end']
            hours = total_duration_ms // 3600000
            minutes = (total_duration_ms % 3600000) // 60000
            seconds = (total_duration_ms % 60000) // 1000
            
            print()
            print("=" * 70)
            print("📊 ESTADÍSTICAS")
            print("=" * 70)
            print(f"Duración total:      {hours:02d}:{minutes:02d}:{seconds:02d}")
            print(f"Total de palabras:   {len(words):,}")
            print(f"Total de segmentos:  {num_segments:,}")
            print(f"Promedio palabras/segmento: {len(words)/num_segments:.1f}")
            print()
        
    except Exception as e:
        print(f"❌ Error durante la conversión: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()