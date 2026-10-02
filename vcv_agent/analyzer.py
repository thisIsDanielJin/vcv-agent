"""Audio analysis: spectrogram generation and feature extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import librosa
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")  # headless rendering


@dataclass
class AudioFeatures:
    """Extracted audio features for LLM feedback."""

    duration_sec: float
    spectral_centroid_hz: float
    estimated_pitch_hz: float
    rms_energy: float
    spectral_flatness: float  # 0 = tonal, 1 = noisy
    onset_count: int
    peak_frequency_hz: float
    silence_ratio: float  # fraction of frames below -60dB

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_spectrogram(wav_path: Path, output_path: Path, sr: int = 48000) -> Path:
    """Generate a mel spectrogram PNG from a WAV file."""
    y, sr_actual = librosa.load(str(wav_path), sr=sr, mono=True)

    S = librosa.feature.melspectrogram(y=y, sr=sr_actual, n_mels=128, fmax=16000)
    S_dB = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots(1, 1, figsize=(12, 4))
    librosa.display.specshow(S_dB, sr=sr_actual, x_axis="time", y_axis="mel", ax=ax, fmax=16000)
    ax.set_title("Mel Spectrogram")
    plt.colorbar(ax.collections[0], ax=ax, format="%+2.0f dB")
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


def extract_features(wav_path: Path, sr: int = 48000) -> AudioFeatures:
    """Extract audio features from a WAV file."""
    y, sr_actual = librosa.load(str(wav_path), sr=sr, mono=True)
    duration = float(len(y) / sr_actual)

    # Spectral centroid (brightness)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr_actual)
    centroid_mean = float(np.mean(centroid))

    # Pitch estimation
    try:
        f0 = librosa.yin(y, fmin=30, fmax=4000, sr=sr_actual)
        # Filter out NaN and very low confidence estimates
        f0_valid = f0[~np.isnan(f0)]
        pitch_mean = float(np.median(f0_valid)) if len(f0_valid) > 0 else 0.0
    except Exception:
        pitch_mean = 0.0

    # RMS energy
    rms = librosa.feature.rms(y=y)
    rms_mean = float(np.mean(rms))

    # Spectral flatness
    flatness = librosa.feature.spectral_flatness(y=y)
    flatness_mean = float(np.mean(flatness))

    # Onset detection
    onsets = librosa.onset.onset_detect(y=y, sr=sr_actual)
    onset_count = int(len(onsets))

    # Peak frequency from FFT
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr_actual)
    mean_spectrum = np.mean(S, axis=1)
    peak_freq = float(freqs[np.argmax(mean_spectrum)])

    # Silence ratio (frames below -60dB)
    rms_frames = rms.flatten()
    silence_threshold = librosa.db_to_power(-60.0)
    silence_ratio = float(np.sum(rms_frames**2 < silence_threshold) / len(rms_frames))

    return AudioFeatures(
        duration_sec=round(duration, 2),
        spectral_centroid_hz=round(centroid_mean, 1),
        estimated_pitch_hz=round(pitch_mean, 1),
        rms_energy=round(rms_mean, 4),
        spectral_flatness=round(flatness_mean, 4),
        onset_count=onset_count,
        peak_frequency_hz=round(peak_freq, 1),
        silence_ratio=round(silence_ratio, 3),
    )


def compare_features(current: AudioFeatures, target: AudioFeatures) -> dict[str, str]:
    """Compute human-readable deltas between current and target features."""
    deltas: dict[str, str] = {}
    for field_name in [
        "spectral_centroid_hz",
        "estimated_pitch_hz",
        "rms_energy",
        "spectral_flatness",
    ]:
        curr_val = getattr(current, field_name)
        tgt_val = getattr(target, field_name)
        if tgt_val == 0:
            continue
        diff = curr_val - tgt_val
        pct = (diff / tgt_val) * 100 if tgt_val != 0 else 0
        direction = "too high" if diff > 0 else "too low"
        deltas[field_name] = f"{curr_val} vs target {tgt_val} ({direction}, {pct:+.0f}%)"
    return deltas
