from __future__ import annotations


def friendly_cast_error(exc: Exception) -> str:
    msg = str(exc).strip()
    lower = msg.lower()

    if not msg:
        return "Cast failed — tap ↻ and try again"

    if "pychromecast is not installed" in lower:
        return "Run: pip install -r requirements.txt"

    if "not installed" in lower and "chromecast" in lower:
        return "Run: pip install pychromecast"

    if "not connected" in lower or "not running" in lower:
        return "Speaker disconnected — tap ↻ then try again"

    if "failed to execute play" in lower:
        return "Speaker could not start playback — tap ↻"

    if "failed to execute" in lower:
        return "Speaker rejected stream — tap ↻"

    if "could not load stream" in lower:
        return msg if len(msg) <= 72 else msg[:69] + "..."

    if "timeout" in lower or "timed out" in lower:
        return "Speaker timed out — tap ↻ and try again"

    if "connection" in lower or "refused" in lower or "unreachable" in lower:
        return "Cannot reach speaker — check Wi-Fi"

    if "ffmpeg" in lower or "alsa" in lower or "error opening input" in lower:
        if "busy" in lower or "resource busy" in lower:
            return "USB audio in use — wait or tap ↻"
        return "Audio input error — check USB_ALSA_DEVICE in .env"

    if len(msg) > 72:
        return msg[:69] + "..."
    return msg
