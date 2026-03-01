from pathlib import Path
import pytest
import shutil

@pytest.fixture
def sample_audio_1m() -> Path:
    """Retorna el path al fixture de 1 minuto. Lo copia a tmp_path en cada test para aislarlo."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_1m.m4a"
    if not fixture_path.exists():
        pytest.fail(f"Fixture no encontrado en {fixture_path}. Ejecuta el comando ffmpeg primero.")
    return fixture_path

@pytest.fixture
def audio_file(tmp_path, sample_audio_1m):
    """Copia el fixture a un directorio temporal para el test."""
    dst = tmp_path / "audio.m4a"
    shutil.copy(sample_audio_1m, dst)
    return dst
