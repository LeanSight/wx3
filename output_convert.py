from __future__ import annotations

import sys
import argparse
from pathlib import Path
from typing import Optional, Union, List
import json
import logging

from constants import SubtitleFormat, GroupingMode
from output_formatters import save_subtitles
from alignment import apply_speaker_names


def configure_simple_logging(level: int = logging.INFO) -> None:
    """
    Configura logging básico con RichHandler.
    """
    from rich.logging import RichHandler
    from rich.console import Console

    console = Console()
    handler = RichHandler(
        console=console,
        show_time=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[handler],
        force=True
    )


logger = logging.getLogger("wx3.convert")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte un archivo de transcripción JSON a otros formatos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python output_convert.py transcription.json -f srt
  python output_convert.py transcription.json -f vtt --speaker-names="Alice,Bob"
  python output_convert.py transcription.json -f txt -o /output/path/
        """
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Ruta al archivo de transcripción (formato JSON)"
    )

    parser.add_argument(
        "-f", "--format",
        dest="output_format",
        type=str,
        choices=[fmt.value for fmt in SubtitleFormat],
        required=True,
        help="Formato de salida (json, srt, vtt, txt)"
    )

    parser.add_argument(
        "-o", "--output",
        dest="output_dir",
        type=str,
        help="Directorio para guardar el archivo convertido"
    )

    parser.add_argument(
        "--output-name",
        dest="output_name",
        type=str,
        help="Nombre del archivo de salida sin extensión"
    )

    parser.add_argument(
        "--speaker-names",
        type=str,
        help="Lista separada por comas de nombres personalizados de hablantes"
    )

    parser.add_argument(
        "--long", "-lg",
        dest="long_segments",
        action="store_true",
        help="Crear segmentos largos (agrupar solo por cambio de speaker)"
    )

    parser.add_argument(
        "--max-chars",
        type=int,
        default=80,
        help="Máximo de caracteres por segmento (solo para agrupación por oraciones, default: 80)"
    )

    parser.add_argument(
        "--max-duration",
        type=float,
        default=10.0,
        help="Máxima duración en segundos por segmento (solo para agrupación por oraciones, default: 10.0)"
    )

    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        parser.error(f"El archivo no existe: {args.input_file}")
    if input_path.suffix.lower() != ".json":
        parser.error("El archivo de entrada debe tener extensión .json")

    return args


def load_chunks(path: Path) -> List[dict]:
    """
    Carga y devuelve la lista de chunks desde un archivo JSON.

    Args:
        path (Path): Ruta al archivo JSON

    Returns:
        List[dict]: Lista de segmentos de transcripción
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("chunks", [])


def convert_transcript(
    input_file: Union[str, Path],
    output_format: str,
    output_dir: Optional[Union[str, Path]] = None,
    output_name: Optional[str] = None,
    speaker_names: Optional[str] = None,
    long_segments: bool = False,
    max_chars: int = 80,
    max_duration: float = 10.0
) -> Path:
    input_path = Path(input_file)
    chunks = load_chunks(input_path)

    if speaker_names:
        names_list = [name.strip() for name in speaker_names.split(",")]
        apply_speaker_names(chunks, names_list)

    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    output_stem = output_name if output_name else input_path.stem
    output_path = output_dir / f"{output_stem}.{output_format}"

    try:
        fmt_enum = SubtitleFormat.from_string(output_format)
        
        # Determinar modo de agrupación usando enum
        grouping_mode = GroupingMode.speaker_only if long_segments else GroupingMode.sentences
        
        save_subtitles(
            transcription_result=None,
            output_file_path=output_path,
            format_type=fmt_enum,
            chunks=chunks,
            with_speaker=True,
            grouping_mode=grouping_mode,
            max_chars=max_chars,
            max_duration_s=max_duration
        )

        logger.info(f"[green]Archivo convertido correctamente:[/] {output_path}")
        logger.info(f"[cyan]Modo de agrupación:[/] {grouping_mode.value}")
        return output_path
    except Exception as e:
        logger.error(f"[red]Error durante conversión:[/] {str(e)}")
        raise


def main() -> int:
    configure_simple_logging()

    try:
        args = parse_arguments()
        convert_transcript(
            input_file=args.input_file,
            output_format=args.output_format,
            output_dir=args.output_dir,
            output_name=args.output_name,
            speaker_names=args.speaker_names,
            long_segments=args.long_segments,
            max_chars=args.max_chars,
            max_duration=args.max_duration
        )
        return 0
    except Exception:
        logger.exception("Error durante la ejecución del conversor")
        return 1


if __name__ == "__main__":
    sys.exit(main())
