import asyncio
from dataclasses import dataclass
from typing import Any

from config_loader import config
from core.logger import logger
from core.theme import error, info, ok, warn

try:
    import speech_recognition as sr
    SR_OK = True
except Exception:
    sr = None
    SR_OK = False

try:
    import pyttsx3
    TTS_OK = True
except Exception:
    pyttsx3 = None
    TTS_OK = False

try:
    import sounddevice as sd
    SD_OK = True
except Exception:
    sd = None
    SD_OK = False


@dataclass
class VoiceDevice:
    index: int
    name: str
    channels: int
    samplerate: int
    is_default: bool = False


class VoiceManager:
    def __init__(self):
        voice_config = config.get("voice", {})
        self.enabled = bool(voice_config.get("enabled", False))
        self.input_enabled = bool(voice_config.get("input_enabled", True))
        self.output_enabled = bool(voice_config.get("output_enabled", True))
        self.input_device_index = voice_config.get("input_device_index")
        self.language = voice_config.get("language", "en-US")
        self.listen_seconds = float(voice_config.get("listen_seconds", 5))
        self.sample_rate = int(voice_config.get("sample_rate", 16000))
        self.rate = int(voice_config.get("rate", 175))
        self.volume = float(voice_config.get("volume", 0.9))
        self.voice_id = voice_config.get("voice_id")
        self.engine = None
        self._speak_lock = asyncio.Lock()

        if self.enabled and self.output_enabled:
            self._ensure_engine()

    def _ensure_engine(self) -> bool:
        if not TTS_OK:
            warn("pyttsx3 is not installed; voice output is unavailable.")
            return False
        if self.engine is not None:
            return True
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", max(0.0, min(self.volume, 1.0)))
            if self.voice_id:
                self.engine.setProperty("voice", self.voice_id)
            return True
        except Exception as exc:
            logger.error(f"TTS initialization failed: {exc}")
            error(f"Voice output failed to initialize: {exc}")
            self.engine = None
            return False

    def enable(self) -> bool:
        self.enabled = True
        if self.output_enabled:
            return self._ensure_engine()
        ok("Voice input enabled.")
        return True

    def disable(self) -> None:
        self.enabled = False
        try:
            if self.engine:
                self.engine.stop()
        except Exception:
            pass

    def set_rate(self, rate: int) -> None:
        self.rate = max(80, min(rate, 320))
        if self.engine:
            self.engine.setProperty("rate", self.rate)

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(volume, 1.0))
        if self.engine:
            self.engine.setProperty("volume", self.volume)

    def set_input_device(self, index: int | None) -> None:
        self.input_device_index = index

    def set_language(self, language: str) -> None:
        self.language = language.strip() or "en-US"

    def set_input_enabled(self, enabled: bool) -> None:
        self.input_enabled = enabled

    def set_output_enabled(self, enabled: bool) -> bool:
        self.output_enabled = enabled
        if enabled and self.enabled:
            return self._ensure_engine()
        return True

    def set_voice(self, voice_id: str) -> bool:
        if not self._ensure_engine():
            return False
        try:
            voices = self.engine.getProperty("voices") or []
            selected = None
            if voice_id.isdigit():
                index = int(voice_id)
                if 0 <= index < len(voices):
                    selected = voices[index].id
            else:
                selected = voice_id
            if not selected:
                return False
            self.voice_id = selected
            self.engine.setProperty("voice", selected)
            return True
        except Exception as exc:
            logger.error(f"Voice selection failed: {exc}")
            return False

    def list_output_voices(self) -> list[dict[str, str]]:
        if not self._ensure_engine():
            return []
        try:
            voices = self.engine.getProperty("voices") or []
        except Exception as exc:
            logger.error(f"Could not list TTS voices: {exc}")
            return []
        return [
            {
                "index": str(index),
                "id": str(getattr(voice, "id", "")),
                "name": str(getattr(voice, "name", "Unknown voice")),
            }
            for index, voice in enumerate(voices)
        ]

    def available(self) -> dict[str, bool]:
        return {
            "speech_recognition": SR_OK,
            "sounddevice": SD_OK,
            "pyttsx3": TTS_OK,
            "tts_engine": self.engine is not None,
        }

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "input_enabled": self.input_enabled,
            "output_enabled": self.output_enabled,
            "input_device_index": self.input_device_index,
            "language": self.language,
            "listen_seconds": self.listen_seconds,
            "sample_rate": self.sample_rate,
            "rate": self.rate,
            "volume": self.volume,
            **self.available(),
        }

    def list_input_devices(self) -> list[VoiceDevice]:
        if not SD_OK:
            return []
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0] if sd.default and sd.default.device else None
        except Exception as exc:
            logger.error(f"Could not query audio devices: {exc}")
            return []

        out: list[VoiceDevice] = []
        for index, device in enumerate(devices):
            channels = int(device.get("max_input_channels", 0))
            if channels <= 0:
                continue
            out.append(VoiceDevice(
                index=index,
                name=str(device.get("name", "Unknown device")),
                channels=channels,
                samplerate=int(device.get("default_samplerate", self.sample_rate)),
                is_default=index == default_input,
            ))
        return out

    async def speak(self, text: str) -> bool:
        if not self.enabled or not self.output_enabled:
            return False
        if not self._ensure_engine():
            return False

        clean_text = " ".join(str(text).split())
        if not clean_text:
            return False

        async with self._speak_lock:
            try:
                await asyncio.to_thread(self._speak_sync, clean_text)
                return True
            except Exception as exc:
                logger.error(f"TTS error: {exc}")
                error(f"Voice output error: {exc}")
                return False

    def _speak_sync(self, text: str) -> None:
        self.engine.say(text)
        self.engine.runAndWait()

    async def listen(self, duration: float | None = None, fallback_to_prompt: bool = False) -> str:
        if not self.enabled or not self.input_enabled:
            if fallback_to_prompt:
                return input("you: ")
            warn("Voice input is disabled.")
            return ""
        if not SR_OK:
            warn("speech_recognition is not installed; voice input is unavailable.")
            return input("you: ") if fallback_to_prompt else ""
        if not SD_OK:
            warn("sounddevice is not installed; microphone input is unavailable.")
            return input("you: ") if fallback_to_prompt else ""

        seconds = duration or self.listen_seconds
        try:
            info(f"Listening for {seconds:g} seconds...")
            audio_bytes = await asyncio.to_thread(self._record_audio, seconds)
        except Exception as exc:
            logger.error(f"Recording error: {exc}")
            error(f"Recording error: {exc}")
            return input("you: ") if fallback_to_prompt else ""

        try:
            recognizer = sr.Recognizer()
            audio = sr.AudioData(audio_bytes, self.sample_rate, 2)
            text = await asyncio.to_thread(recognizer.recognize_google, audio, language=self.language)
            ok(f"Heard: {text}")
            return text
        except sr.UnknownValueError:
            warn("Could not understand the recording.")
            return ""
        except sr.RequestError as exc:
            logger.error(f"Recognition service error: {exc}")
            error(f"Speech recognition service error: {exc}")
            return ""
        except Exception as exc:
            logger.error(f"Recognition error: {exc}")
            error(f"Recognition error: {exc}")
            return ""

    def _record_audio(self, seconds: float) -> bytes:
        device = self.input_device_index
        recording = sd.rec(
            int(seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            device=device,
        )
        sd.wait()
        return recording.tobytes()
