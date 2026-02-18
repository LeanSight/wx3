"""
Script to enhance audio using ClearerVoice-Studio with speech enhancement models.

Supports multiple audio formats (WAV, M4A, MP3, FLAC, etc.)
Automatically converts to WAV if needed for processing.
Uses CUDA GPU acceleration when available.
"""
import argparse
import os
import sys
from pathlib import Path
from clearvoice import ClearVoice
from pydub import AudioSegment
import torch


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Enhance audio quality using AI-powered speech enhancement',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s audio.m4a
  %(prog)s audio.wav --compress                     # Output AAC M4A
  %(prog)s audio.mp3 -m FRCRN_SE_16K --compress     # Fast model + compress
  %(prog)s audio.flac --compress --bitrate 256k     # Custom bitrate
  %(prog)s audio.m4a --compress --keep-wav          # Keep both WAV and M4A

Available models:
  - MossFormer2_SE_48K (default, best quality for 48kHz)
  - FRCRN_SE_16K (fast, good for 16kHz)
  - MossFormerGAN_SE_16K (balanced, 16kHz)

Compression options:
  - Default: No compression (output WAV)
  - --compress: AAC 320kbps (near-transparent quality, ~85%% size reduction)
  - --bitrate 256k: AAC 256kbps (excellent quality, ~90%% size reduction)
  - --bitrate 192k: AAC 192kbps (very good quality, ~93%% size reduction)
        """
    )

    parser.add_argument(
        'input',
        type=str,
        help='Input audio file (supports: WAV, M4A, MP3, FLAC, AAC, OGG, etc.)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output enhanced audio file (default: <input>_enhanced.m4a if --compress, else .wav)'
    )

    parser.add_argument(
        '-m', '--model',
        type=str,
        default='MossFormer2_SE_48K',
        choices=['MossFormer2_SE_48K', 'FRCRN_SE_16K', 'MossFormerGAN_SE_16K'],
        help='Speech enhancement model to use (default: MossFormer2_SE_48K)'
    )

    parser.add_argument(
        '--compress',
        action='store_true',
        help='Compress output to AAC M4A format (320kbps for maximum quality)'
    )

    parser.add_argument(
        '--bitrate',
        type=str,
        default='320k',
        help='AAC bitrate when using --compress (default: 320k for high quality)'
    )

    parser.add_argument(
        '--keep-wav',
        action='store_true',
        help='Keep uncompressed WAV file when using --compress'
    )

    parser.add_argument(
        '--keep-temp',
        action='store_true',
        help='Keep temporary WAV file after processing'
    )

    parser.add_argument(
        '--temp-dir',
        type=str,
        default=None,
        help='Directory for temporary files (default: same as input file)'
    )

    return parser.parse_args()


def get_audio_format(file_path):
    """Detect audio format from file extension."""
    ext = Path(file_path).suffix.lower()
    format_map = {
        '.wav': 'wav',
        '.m4a': 'm4a',
        '.mp3': 'mp3',
        '.flac': 'flac',
        '.aac': 'aac',
        '.ogg': 'ogg',
        '.opus': 'opus',
        '.wma': 'wma',
        '.aiff': 'aiff',
        '.aifc': 'aifc'
    }
    return format_map.get(ext, None)


def detect_cuda():
    """Detect and display CUDA GPU information."""
    cuda_available = torch.cuda.is_available()

    print("\n" + "="*60)
    print("GPU ACCELERATION STATUS")
    print("="*60)

    if cuda_available:
        device_name = torch.cuda.get_device_name(0)
        device_count = torch.cuda.device_count()
        cuda_version = torch.version.cuda

        print(f"[OK] CUDA is AVAILABLE")
        print(f"GPU Device: {device_name}")
        print(f"GPU Count: {device_count}")
        print(f"CUDA Version: {cuda_version}")
        print(f"PyTorch Version: {torch.__version__}")
        print(f"Status: Models will run on GPU (accelerated)")
    else:
        print(f"[INFO] CUDA is NOT AVAILABLE")
        print(f"PyTorch Version: {torch.__version__}")
        print(f"Status: Models will run on CPU (slower)")

    print("="*60 + "\n")

    return cuda_available


def convert_to_wav(input_file, output_wav, input_format=None):
    """Convert audio file to WAV format."""
    print(f"Converting {Path(input_file).name} to WAV format...")

    if input_format is None:
        input_format = get_audio_format(input_file)

    if input_format is None:
        print(f"Warning: Unknown format, attempting auto-detection...")
        audio = AudioSegment.from_file(input_file)
    else:
        audio = AudioSegment.from_file(input_file, format=input_format)

    audio.export(output_wav, format="wav")
    print(f"[OK] Converted to {Path(output_wav).name}")
    return output_wav


def compress_to_aac(wav_file, output_m4a, bitrate='320k'):
    """
    Compress WAV to AAC M4A format with high quality.

    Args:
        wav_file: Path to input WAV file
        output_m4a: Path to output M4A file
        bitrate: AAC bitrate (default: 320k for maximum quality)
    """
    print(f"\nCompressing to AAC M4A format...")
    print(f"Bitrate: {bitrate}")

    wav_path = Path(wav_file)
    m4a_path = Path(output_m4a)

    try:
        # Load WAV file
        audio = AudioSegment.from_wav(str(wav_path))

        # Export as M4A with AAC codec
        audio.export(
            str(m4a_path),
            format='ipod',  # M4A format
            codec='aac',
            bitrate=bitrate,
            parameters=['-q:a', '0']  # Highest quality AAC encoding
        )

        # Calculate compression ratio
        wav_size = wav_path.stat().st_size / (1024*1024)
        m4a_size = m4a_path.stat().st_size / (1024*1024)
        compression_ratio = (1 - m4a_size/wav_size) * 100

        print(f"[OK] Compressed: {wav_size:.1f} MB -> {m4a_size:.1f} MB "
              f"({compression_ratio:.1f}% reduction)")

        return str(m4a_path)

    except Exception as e:
        raise RuntimeError(f"Failed to compress to AAC: {e}")


def enhance_audio(input_file, output_file=None, model='MossFormer2_SE_48K',
                  keep_temp=False, temp_dir=None, compress=False,
                  bitrate='320k', keep_wav=False):
    """
    Enhance audio quality using ClearerVoice-Studio.

    Args:
        input_file: Path to input audio file
        output_file: Path to output enhanced audio file (optional)
        model: Model name to use for enhancement
        keep_temp: Whether to keep temporary WAV files
        temp_dir: Directory for temporary files
        compress: Whether to compress output to AAC M4A
        bitrate: AAC bitrate when compressing (default: 320k)
        keep_wav: Keep uncompressed WAV when compressing

    Returns:
        Path to enhanced audio file (or files if keep_wav=True)
    """
    input_path = Path(input_file).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Determine output file path
    if output_file is None:
        if compress:
            output_path = input_path.parent / f"{input_path.stem}_enhanced.m4a"
            wav_output_path = input_path.parent / f"{input_path.stem}_enhanced.wav"
        else:
            output_path = input_path.parent / f"{input_path.stem}_enhanced.wav"
            wav_output_path = output_path
    else:
        output_path = Path(output_file).resolve()
        if compress and output_path.suffix.lower() != '.m4a':
            # User specified output but it's not .m4a, create WAV path
            wav_output_path = output_path.parent / f"{output_path.stem}.wav"
        else:
            wav_output_path = output_path

    # Determine temp directory
    if temp_dir is None:
        temp_directory = input_path.parent
    else:
        temp_directory = Path(temp_dir).resolve()
        temp_directory.mkdir(parents=True, exist_ok=True)

    # Detect CUDA availability
    cuda_available = detect_cuda()

    # Check if input is already WAV
    input_format = get_audio_format(input_path)
    needs_conversion = input_format != 'wav'

    if needs_conversion:
        temp_wav = temp_directory / f"{input_path.stem}_temp.wav"
        processing_file = convert_to_wav(str(input_path), str(temp_wav), input_format)
    else:
        processing_file = str(input_path)
        temp_wav = None

    # Initialize ClearVoice
    print(f"Initializing ClearVoice with {model} model...")
    try:
        clear_voice = ClearVoice(task='speech_enhancement', model_names=[model])
    except Exception as e:
        if temp_wav and not keep_temp:
            temp_wav.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to initialize ClearVoice: {e}")

    # Process the audio
    print(f"\nProcessing audio with speech enhancement...")
    print(f"Model: {model}")
    print(f"Device: {'GPU (CUDA)' if cuda_available else 'CPU'}")
    print(f"Input: {input_path.name}")

    try:
        output_audio = clear_voice(input_path=processing_file, online_write=False)

        # Save enhanced audio (always to WAV first)
        print(f"\nSaving enhanced audio to WAV...")
        clear_voice.write(output_audio, output_path=str(wav_output_path))

        # Compress to AAC if requested
        if compress:
            print(f"\n{'='*60}")
            print(f"COMPRESSION TO AAC M4A")
            print(f"{'='*60}")

            compress_to_aac(str(wav_output_path), str(output_path), bitrate)

            # Remove WAV if not keeping
            if not keep_wav and wav_output_path != output_path:
                wav_size_mb = wav_output_path.stat().st_size / (1024*1024)
                wav_output_path.unlink()
                print(f"[OK] WAV file removed ({wav_size_mb:.1f} MB freed)")

        print(f"\n{'='*60}")
        print(f"[SUCCESS] Enhancement completed successfully!")
        print(f"{'='*60}")
        print(f"Original file:  {input_path} ({input_path.stat().st_size / (1024*1024):.1f} MB)")

        if compress and keep_wav:
            print(f"Enhanced WAV:   {wav_output_path} ({wav_output_path.stat().st_size / (1024*1024):.1f} MB)")
            print(f"Enhanced M4A:   {output_path} ({output_path.stat().st_size / (1024*1024):.1f} MB)")
        else:
            print(f"Enhanced file:  {output_path} ({output_path.stat().st_size / (1024*1024):.1f} MB)")
            final_size = output_path.stat().st_size / (1024*1024)
            orig_size = input_path.stat().st_size / (1024*1024)
            size_change = ((final_size - orig_size) / orig_size) * 100
            if size_change > 0:
                print(f"Size change:    +{size_change:.1f}% (higher quality)")
            else:
                print(f"Size reduction: {abs(size_change):.1f}%")

        # Cleanup temporary files
        if temp_wav and not keep_temp:
            temp_wav.unlink(missing_ok=True)
            print(f"\n[OK] Temporary file cleaned up")
        elif temp_wav and keep_temp:
            print(f"\nTemporary file kept: {temp_wav}")

        if compress and keep_wav:
            return str(output_path), str(wav_output_path)
        else:
            return str(output_path)

    except Exception as e:
        # Cleanup on error
        if temp_wav and not keep_temp:
            temp_wav.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to enhance audio: {e}")


def main():
    """Main entry point."""
    args = parse_arguments()

    try:
        enhance_audio(
            input_file=args.input,
            output_file=args.output,
            model=args.model,
            keep_temp=args.keep_temp,
            temp_dir=args.temp_dir,
            compress=args.compress,
            bitrate=args.bitrate,
            keep_wav=args.keep_wav
        )
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
