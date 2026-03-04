from pathlib import Path
import pytest
import shutil


@pytest.fixture
def audio_fixture_path() -> Path:
    """Path al fixture de audio real para tests de acceptance."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_1m.m4a"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")
    return fixture_path


@pytest.fixture
def sample_audio_1m(audio_fixture_path) -> Path:
    return audio_fixture_path


@pytest.fixture
def audio_file(tmp_path, sample_audio_1m):
    """Copia el fixture a un directorio temporal para el test."""
    dst = tmp_path / "audio.m4a"
    shutil.copy(sample_audio_1m, dst)
    return dst
