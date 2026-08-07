from pydub import AudioSegment, silence, effects


# -------------------------------------------------------------------
# Funções individuais
# -------------------------------------------------------------------

def normalizar_audio(audio: AudioSegment, target_dbfs: float = -3.0) -> AudioSegment:
    """Normaliza o volume para um nível consistente."""
    return effects.normalize(audio, headroom=abs(target_dbfs))


def aplicar_compressao(audio: AudioSegment) -> AudioSegment:
    """Nivela a dinâmica da voz — reduz picos, levanta partes baixas."""
    return effects.compress_dynamic_range(audio)


def remover_silencios_extremos(audio: AudioSegment, silence_thresh: int = -45) -> AudioSegment:
    """Remove silêncio no início e no fim do chunk."""
    start_trim = silence.detect_leading_silence(audio, silence_threshold=silence_thresh)
    end_trim   = silence.detect_leading_silence(audio.reverse(), silence_threshold=silence_thresh)
    duration   = len(audio)
    trimmed    = audio[start_trim : duration - end_trim]
    # Garante que não retorna vazio se o áudio for muito curto
    #return trimmed if len(trimmed) > 100 else audio
    return audio


def aplicar_equalizacao_voz(audio: AudioSegment) -> AudioSegment:
    """
    EQ simples para dar corpo à voz do Oráculo:
      - Corta rumble abaixo de 80 Hz (high_pass)
      - Sobrepõe um boost suave nos médios-graves (180-300 Hz)
        sem remover os agudos — mantém clareza e peso ao mesmo tempo.

    CORREÇÃO do bug original:
      low_pass_filter(200) eliminava médios e agudos inteiros,
      deixando só graves abafados. Aqui fazemos o oposto:
      cortamos apenas o ruído de fundo (< 80 Hz) e adicionamos
      calor nos médios-graves via overlay com gain controlado.
    """
    # 1. Remove ruído de fundo / rumble (abaixo de 80 Hz)
    audio_limpo = audio.high_pass_filter(80)

    # 2. Isola a faixa de calor da voz (médios-graves)
    camada_graves = audio_limpo.low_pass_filter(300).apply_gain(2)

    # 3. Sobrepõe o calor sobre o áudio limpo (não substitui)
    return audio_limpo.overlay(camada_graves)


def inserir_efeito_sonoro(
    audio_principal: AudioSegment,
    caminho_efeito: str,
    posicao_ms: int,
    volume_ajuste: int = -10
) -> AudioSegment:
    """Sobrepõe um efeito sonoro na posição indicada (em ms)."""
    efeito = AudioSegment.from_file(caminho_efeito)
    efeito = efeito + volume_ajuste
    return audio_principal.overlay(efeito, position=posicao_ms)


# -------------------------------------------------------------------
# Função principal — use esta nos outros módulos
# -------------------------------------------------------------------

def processar_chunk(chunk: AudioSegment) -> AudioSegment:
    """
    Pipeline completo de pós-processamento para cada chunk de voz gerado
    pelo XTTS. Ordem importa:
      1. Remove silêncios das bordas      -> evita pausas duplas na concatenação
      2. Compressão dinâmica              -> nivela volume entre chunks
      3. EQ de voz                        -> corpo sem afogar agudos
      4. Normalização final               -> nível de saída consistente (-3 dBFS)
    """
    #audio = remover_silencios_extremos(chunk)
    audio = aplicar_compressao(chunk)
    audio = aplicar_equalizacao_voz(audio)
    audio = normalizar_audio(audio)
    return audio                