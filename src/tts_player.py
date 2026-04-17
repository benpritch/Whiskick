import os
import subprocess
import tempfile
import threading
import logging
import numpy as np
import soundfile as sf
import requests

logger = logging.getLogger(__name__)

_ONNX_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "tiny-tts", "onnx")
_ONNX_BASE = "https://raw.githubusercontent.com/tronghieuit/tiny-tts/develop/onnx"
_ONNX_FILES = ["text_encoder.onnx", "duration_predictor.onnx", "flow.onnx", "decoder.onnx"]

_SAMPLING_RATE = 44100
_SPK2ID = {"MALE": 0}


def _ensure_nltk_data():
    import nltk
    for resource in ("averaged_perceptron_tagger_eng", "averaged_perceptron_tagger", "cmudict"):
        nltk.download(resource, quiet=True)


def _patch_tiny_tts():
    """Register a stub for tiny_tts before submodule imports so its __init__.py
    (which unconditionally imports torch) is never executed."""
    import sys, types, importlib.util
    if "tiny_tts" in sys.modules:
        return
    spec = importlib.util.find_spec("tiny_tts")
    if spec is None:
        raise ImportError("tiny_tts not installed — run: pip install tiny-tts --no-deps")
    stub = types.ModuleType("tiny_tts")
    stub.__path__ = list(spec.submodule_search_locations)
    stub.__package__ = "tiny_tts"
    stub.__spec__ = spec
    sys.modules["tiny_tts"] = stub


def _insert_blanks(lst, item=0):
    result = [item] * (len(lst) * 2 + 1)
    result[1::2] = lst
    return result


def _ensure_onnx_models():
    os.makedirs(_ONNX_CACHE, exist_ok=True)
    for fname in _ONNX_FILES:
        path = os.path.join(_ONNX_CACHE, fname)
        if not os.path.exists(path):
            url = f"{_ONNX_BASE}/{fname}"
            logger.info(f"Downloading {fname}...")
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
    return _ONNX_CACHE


class _Engine:
    def __init__(self):
        import onnxruntime as ort
        ort.set_default_logger_severity(3)  # suppress warnings (GPU discovery noise)
        onnx_dir = _ensure_onnx_models()
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = os.cpu_count() or 4
        providers = ["CPUExecutionProvider"]

        def _sess(name):
            return ort.InferenceSession(
                os.path.join(onnx_dir, name), sess_options=opts, providers=providers
            )

        self._enc  = _sess("text_encoder.onnx")
        self._dp   = _sess("duration_predictor.onnx")
        self._flow = _sess("flow.onnx")
        self._dec  = _sess("decoder.onnx")

    def synthesize(self, text: str, output_path: str, speed: float = 1.0):
        _patch_tiny_tts()
        _ensure_nltk_data()
        from tiny_tts.text.english import normalize_text, grapheme_to_phoneme
        from tiny_tts.text import phonemes_to_ids

        phones, tones, _ = grapheme_to_phoneme(normalize_text(text))
        phone_ids, tone_ids, lang_ids = phonemes_to_ids(phones, tones, "EN")

        phone_ids = _insert_blanks(phone_ids)
        tone_ids  = _insert_blanks(tone_ids)
        lang_ids  = _insert_blanks(lang_ids)

        T = len(phone_ids)
        x       = np.array(phone_ids, dtype=np.int64)[None, :]
        x_len   = np.array([T], dtype=np.int64)
        tone    = np.array(tone_ids, dtype=np.int64)[None, :]
        lang    = np.array(lang_ids, dtype=np.int64)[None, :]
        bert    = np.zeros((1, 1024, T), dtype=np.float32)
        ja_bert = np.zeros((1, 768,  T), dtype=np.float32)
        sid     = np.array([_SPK2ID.get("MALE", 0)], dtype=np.int64)

        x_enc, m_p, logs_p, x_mask, g = self._enc.run(None, {
            "phone_ids": x, "phone_lengths": x_len, "tone_ids": tone,
            "language_ids": lang, "bert": bert, "ja_bert": ja_bert, "speaker_id": sid,
        })

        logw = self._dp.run(None, {"x": x_enc, "x_mask": x_mask, "g": g})[0]

        w = np.exp(logw) * x_mask * (1.0 / speed)
        w_ceil = np.ceil(w)
        y_len = max(1, int(w_ceil.sum()))
        y_lens = np.array([y_len], dtype=np.int64)

        y_mask = (np.arange(y_len, dtype=np.float32)[None, :] < y_lens[:, None]).astype(np.float32)[:, None, :]

        # Monotonic alignment path
        dur = w_ceil[0, 0]
        cum = np.cumsum(dur)
        cum_prev = np.pad(cum[:-1], (1, 0))
        frame_idx = np.arange(y_len, dtype=np.float32)[:, None]
        attn = ((frame_idx >= cum_prev) & (frame_idx < cum)).astype(np.float32)[None, None, :, :]
        attn = attn * (y_mask[:, :, :, None] * x_mask[:, :, None, :])

        m_p_exp    = np.matmul(attn[:, 0], m_p.transpose(0, 2, 1)).transpose(0, 2, 1)
        logs_p_exp = np.matmul(attn[:, 0], logs_p.transpose(0, 2, 1)).transpose(0, 2, 1)
        z_p = m_p_exp + np.random.randn(*m_p_exp.shape).astype(np.float32) * np.exp(logs_p_exp) * 0.667

        z = self._flow.run(None, {"z_p": z_p, "y_mask": y_mask.astype(np.float32), "g": g})[0]
        audio = self._dec.run(None, {"z": (z * y_mask).astype(np.float32), "g": g})[0]

        sf.write(output_path, audio[0, 0], _SAMPLING_RATE)


class TTSPlayer:
    def __init__(self):
        self._card_index = self._find_wm8960_card()
        self._setup_mixer()
        self._engine = None
        self._lock = threading.Lock()

    def _find_wm8960_card(self):
        try:
            with open("/proc/asound/cards") as f:
                for line in f:
                    if "wm8960" in line.lower():
                        return int(line.strip().split()[0])
        except Exception:
            pass
        return 1

    def _setup_mixer(self):
        card = str(self._card_index)
        cmds = [
            ['amixer', '-c', card, 'sset', 'Left Output Mixer PCM', 'on'],
            ['amixer', '-c', card, 'sset', 'Right Output Mixer PCM', 'on'],
            ['amixer', '-c', card, 'sset', 'Speaker', '100%'],
            ['amixer', '-c', card, 'sset', 'Playback', '100%'],
        ]
        for cmd in cmds:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except Exception:
                pass

    def _get_engine(self):
        if self._engine is None:
            self._engine = _Engine()
        return self._engine

    def speak_async(self, text: str):
        threading.Thread(target=self._speak_task, args=(text,), daemon=True).start()

    def _speak_task(self, text: str):
        with self._lock:
            tmp_path = None
            try:
                engine = self._get_engine()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name
                engine.synthesize(text, tmp_path)
                hw_device = f"plughw:{self._card_index},0"
                subprocess.run(
                    ["aplay", "-D", hw_device, tmp_path],
                    capture_output=True, timeout=60
                )
            except Exception as e:
                logger.error(f"TTS error: {e}")
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
