#!/usr/bin/env python3
"""
Offline audio transcriber using OpenAI Whisper.

Supports 99+ languages and handles multiple languages within the same audio.
The model automatically detects the language per segment.

Usage:
    python transcriber.py <audio_file> [--model <model_name>] [--output <output_file>]

Models (larger = more accurate, slower):
    tiny, base, small, medium, large, large-v2, large-v3 (default: medium)
"""

import argparse
import sys
from pathlib import Path


def transcribe(audio_path: str, model_name: str = "medium") -> dict:
    """
    Transcribe an audio file using Whisper.

    Returns a dict with:
        - text: full transcription
        - language: detected primary language
        - segments: list of timed segments, each with detected language
    """
    try:
        import whisper
    except ImportError:
        print("ERROR: whisper not installed. Run: pip install openai-whisper", file=sys.stderr)
        sys.exit(1)

    audio_path = Path(audio_path)
    if not audio_path.exists():
        print(f"ERROR: File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading Whisper model '{model_name}'... (downloads on first use)")
    model = whisper.load_model(model_name)

    print(f"Transcribing: {audio_path}")
    # detect_language=True per segment is done automatically by Whisper
    result = model.transcribe(str(audio_path), task="transcribe", verbose=False)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "language": seg.get("language", result.get("language", "unknown")),
        })

    return {
        "text": result["text"].strip(),
        "language": result.get("language", "unknown"),
        "segments": segments,
    }


def format_output(result: dict, show_segments: bool = True) -> str:
    lines = []
    lines.append(f"[Detected primary language: {result['language']}]")
    lines.append("")
    lines.append("=== Full Transcription ===")
    lines.append(result["text"])

    if show_segments and result["segments"]:
        # Only show segment-level language detail if multiple languages appear
        languages_found = {s["language"] for s in result["segments"]}
        if len(languages_found) > 1:
            lines.append("")
            lines.append("=== Segments with Language Detection ===")
            for seg in result["segments"]:
                start = f"{seg['start']:.1f}s"
                end = f"{seg['end']:.1f}s"
                lines.append(f"[{start} → {end}] [{seg['language']}] {seg['text']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Offline audio transcriber with multilingual support (Whisper)"
    )
    parser.add_argument("audio", help="Path to the audio file (mp3, wav, m4a, ogg, flac, …)")
    parser.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Whisper model to use (default: medium). Use large-v3 for best accuracy.",
    )
    parser.add_argument(
        "--output",
        help="Save transcription to this file (optional). Prints to stdout if omitted.",
    )
    parser.add_argument(
        "--no-segments",
        action="store_true",
        help="Skip per-segment language breakdown in output.",
    )
    args = parser.parse_args()

    result = transcribe(args.audio, model_name=args.model)
    formatted = format_output(result, show_segments=not args.no_segments)

    if args.output:
        Path(args.output).write_text(formatted, encoding="utf-8")
        print(f"Transcription saved to: {args.output}")
    else:
        print()
        print(formatted)


if __name__ == "__main__":
    main()
