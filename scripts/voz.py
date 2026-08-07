import os
import torch
import librosa
from TTS.api import TTS
import TTS.tts.models.xtts as xtts_module
from pydub import AudioSegment

from scripts.audio_fx import processar_chunk
from scripts.utils import dividir_texto  # << split semântico

try:
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
    from TTS.config.shared_configs import BaseDatasetConfig
    torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])
except:
    pass


def load_audio_librosa(file_path, sr):
    audio, _ = librosa.load(file_path, sr=sr)
    return torch.from_numpy(audio).unsqueeze(0)

xtts_module.load_audio = load_audio_librosa

_MODELO_TTS = None
device = "cuda" if torch.cuda.is_available() else "cpu"


def _get_model():
    """Singleton — carrega o modelo XTTS apenas uma vez na memória."""
    global _MODELO_TTS
    if _MODELO_TTS is None:
        print(f"🧠 Carregando modelo XTTS v2 no {device}...")
        _MODELO_TTS = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to(device)
    return _MODELO_TTS


def gerar_audio_oraculo(texto, nome_projeto, temperature=0.88, speed=1.12, sufixo="", pasta_referencia="voz", output_dir: str | None = None):
    """
    pasta_referencia: subpasta dentro de inputs/ com os WAVs de referência.
    Default "voz" mantém o comportamento atual sem quebrar nada.
    """
    ROOT_DIR = os.getcwd()
    if output_dir:
        pasta_saida = str(output_dir)
    else:
        pasta_saida = os.path.join(ROOT_DIR, "inputs", "vozes_geradas")
    pasta_temp  = os.path.join(ROOT_DIR, "temp")
    pasta_voz   = os.path.join(ROOT_DIR, "inputs", pasta_referencia)

    os.makedirs(pasta_saida, exist_ok=True)
    os.makedirs(pasta_temp,  exist_ok=True)

    # monta nome base com sufixo
    nome_base = f"{nome_projeto}{sufixo}" if sufixo else nome_projeto

    # garante nome único — nunca sobrescreve
    caminho_final = os.path.join(pasta_saida, f"{nome_base}.wav")
    contador = 1
    while os.path.exists(caminho_final):
        caminho_final = os.path.join(pasta_saida, f"{nome_base}_{contador:02d}.wav")
        contador += 1

    referencias = [
        os.path.join(pasta_voz, f)
        for f in os.listdir(pasta_voz)
        if f.endswith('.wav')
    ]
    if not referencias:
        raise FileNotFoundError("❌ Nenhuma voz de referência encontrada em inputs/voz/")

    chunks = dividir_texto(texto)
    tts    = _get_model()
    audio_combinado = AudioSegment.empty()

    print(f"🎙️ Narrando {len(chunks)} blocos → {os.path.basename(caminho_final)}")

    for i, (frase, pausa_ms) in enumerate(chunks):
        path_temp = os.path.join(pasta_temp, f"chunk_{nome_base}_{i}.wav")
        try:
            tts.tts_to_file(
                text=frase,
                file_path=path_temp,
                speaker_wav=referencias,
                language="pt",
                temperature=temperature,
                top_p=0.85,
                speed=speed
            )
            segmento = AudioSegment.from_wav(path_temp)
            segmento_tratado = processar_chunk(segmento)
            audio_combinado += segmento_tratado + AudioSegment.silent(duration=pausa_ms)
        except Exception as e:
            print(f"⚠️ Erro ao narrar bloco {i} ('{frase[:40]}...'): {e}")
        finally:
            if os.path.exists(path_temp):
                try:
                    os.remove(path_temp)
                except:
                    pass

    duracao_segundos = len(audio_combinado) / 1000.0
    if duracao_segundos > 75:
        print(f"⚠️  CUIDADO: Áudio com {duracao_segundos:.2f}s — pode ser longo para o TikTok.")
    else:
        print(f"⚡ RITMO OK: {duracao_segundos:.2f}s.")

    audio_combinado.export(caminho_final, format="wav")
    print(f"✓ Salvo em: {caminho_final}")
    return caminho_final