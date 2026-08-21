# scripts_v2/video_v2.py
import os
import random
import cv2
from moviepy.editor import (
    AudioFileClip, ImageClip, VideoFileClip,
    CompositeVideoClip, CompositeAudioClip, TextClip,
    vfx, afx
)

from PIL import Image, ImageDraw, ImageFont
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def gerar_arquivo_legenda(roteiro_cenas: list, cartas: list, caminho_saida_txt: str):
    """Gera um arquivo legenda.txt na pasta do projeto final."""
    cartas_fmt = ", ".join([c.replace("_", " ").title() for c in cartas if isinstance(c, str)])
    
    # Pega a primeira frase como gancho e a última como CTA
    gancho = roteiro_cenas[0].get("texto", "") if roteiro_cenas else ""
    cta = roteiro_cenas[-1].get("texto", "") if len(roteiro_cenas) > 1 else ""

    hashtag_carta = cartas[0].replace('_', '') if cartas else 'tarot'

    conteudo = f"""✨ ORÁCULO DA MENSAGEM: {cartas_fmt.upper()} ✨

"{gancho}"

---
💭 O que as cartas revelam hoje:
{cta}

👇 Deixe um 'AMÉM' ou comente para se conectar com essa energia!
🔗 Leitura completa e personalizada no link da bio.

#tarot #oraculo #tarotdiario #espiritualidade #mensagemdodia #cartasdotarot #{hashtag_carta}
"""
    with open(caminho_saida_txt, "w", encoding="utf-8") as f:
        f.write(conteudo)


def extrair_thumbnail(caminho_video: str, segundo: float = 1.0) -> np.ndarray | None:
    """Extrai um frame do vídeo para usar como thumbnail no Streamlit."""
    try:
        cap = cv2.VideoCapture(caminho_video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * segundo))
        ret, frame = cap.read()
        cap.release()
        if ret:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    except Exception:
        pass
    return None


def listar_backgrounds() -> list[str]:
    pasta = os.path.join(BASE_DIR, "inputs", "videos_fundo")
    if not os.path.exists(pasta):
        return []
    return [
        os.path.join(pasta, f)
        for f in sorted(os.listdir(pasta))
        # Agora aceita .mp4, .mp4, .mov e .MOV
        if f.lower().endswith(('.mp4', '.mov'))
    ]


def listar_musicas() -> list[str]:
    pasta = os.path.join(BASE_DIR, "inputs", "audio_assets")
    if not os.path.exists(pasta):
        return []
    return [
        os.path.join(pasta, f)
        for f in sorted(os.listdir(pasta))
        if f.endswith(('.mp3', '.wav'))
    ]

def garantir_fps(clips: list, fps: int = 30) -> list:
    resultado = []
    for clip in clips:
        try:
            if getattr(clip, 'fps', None) is None or clip.fps == 0:
                clip = clip.set_fps(fps)
        except Exception:
            clip = clip.set_fps(fps)
        resultado.append(clip)
    return resultado


def remover_acentos(texto: str) -> str:
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def criar_fundo_base(bg_path: str, duracao: float, inicio: float):
    bg = VideoFileClip(bg_path, audio=False)
    fps_original = bg.fps if (bg.fps and bg.fps > 0) else 30 ### SEGURO DE FPS ###
    
    print(f"bg fps antes resize: {bg.fps} | {bg_path}")
    if bg.duration < duracao + inicio:
        bg = bg.loop(duration=duracao + inicio)
    bg = bg.subclip(inicio, inicio + duracao)
    bg = bg.resize((1080, 1920))
    
    # Força o retorno do FPS que pode sumir no resize do MoviePy
    bg = bg.set_fps(fps_original)
    print(f"bg fps depois resize: {bg.fps}")
    return bg.set_start(inicio)


def criar_texto_pil(texto: str, tamanho_fonte: int = 55,
                    cor=(255, 255, 255), sombra=True) -> ImageClip:
    
    pasta_fonts = os.path.join(BASE_DIR, "inputs", "fonts")
    fonte_path  = None
    
    if os.path.exists(pasta_fonts):
        fontes_disponiveis = [
            f for f in os.listdir(pasta_fonts)
            if f.endswith(('.ttf', '.otf'))
        ]
        if fontes_disponiveis:
            fonte_path = os.path.join(pasta_fonts, fontes_disponiveis[0])

    try:
        if fonte_path and os.path.exists(fonte_path):
            fonte = ImageFont.truetype(fonte_path, tamanho_fonte)
        else:
            raise FileNotFoundError("Nenhuma fonte encontrada")
    except Exception as e:
        print(f"✗ Fonte não carregada ({e}) — usando default aumentada")
        try:
            from PIL import ImageFont as PILFont
            fonte = PILFont.load_default(size=tamanho_fonte)
        except Exception:
            fonte = ImageFont.load_default()

    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox    = dummy.textbbox((0, 0), texto, font=fonte)
    w       = bbox[2] - bbox[0] + 40
    h       = bbox[3] - bbox[1] + 40

    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if sombra:
        draw.text((15, 15), texto, font=fonte, fill=(0, 0, 0, 180), align="center")
    draw.text((13, 13), texto, font=fonte, fill=cor, align="center")

    img_clip = ImageClip(np.array(img), ismask=False)
    return img_clip.set_fps(30) ### ASSEGURA FPS NA ORIGEM DO TEXTO ###



def _calcular_duracoes(cenas: list, duracao_total: float) -> list[float]:
    CTA_MINIMO = 3.0
    n = len(cenas)
    if n == 0:
        return []

    ctas = [i for i, c in enumerate(cenas) if c.get('tipo') == 'cta_integrado']
    tempo_cta = CTA_MINIMO * len(ctas)
    tempo_resto = duracao_total - tempo_cta

    total_chars_resto = sum(
        len(c.get('texto', ''))
        for i, c in enumerate(cenas)
        if i not in ctas
    )

    duracoes = []
    for i, cena in enumerate(cenas):
        if i in ctas:
            duracoes.append(CTA_MINIMO)
        else:
            chars = len(cena.get('texto', ''))
            proporcao = chars / total_chars_resto if total_chars_resto > 0 else 1 / n
            duracoes.append(tempo_resto * proporcao)

    return duracoes


def gerar_legendas_pil(audio_path: str) -> list:
    """
    Gera legendas sincronizadas via Whisper.
    3 palavras por bloco, posicionadas na parte inferior do vídeo.
    """
    try:
        import whisper
        print("🎙️ Gerando legendas com Whisper...")
        model  = whisper.load_model("small")
        result = model.transcribe(
            audio_path,
            fp16=False,
            language='pt',
            word_timestamps=True
        )
    except Exception as e:
        print(f"⚠️ Whisper não disponível: {e} — vídeo sem legendas.")
        return []

    legendas           = []
    palavras_por_bloco = 3

    for segment in result.get('segments', []):
        if 'words' not in segment:
            continue

        palavras = segment['words']

        for i in range(0, len(palavras), palavras_por_bloco):
            grupo       = palavras[i:i + palavras_por_bloco]
            texto_bloco = " ".join([w['word'].strip().upper() for w in grupo])
            start_t    = grupo[0]['start']
            end_t      = grupo[-1]['end']
            duracao    = max(end_t - start_t, 0.1)

            try:
                txt_clip = (
                    criar_texto_pil(texto_bloco, tamanho_fonte=55)
                    .set_fps(30)
                    .set_start(start_t)             # 1. CORRIGIDO: Define o tempo exato de entrada da legenda
                    .set_duration(duracao)
                    .set_position(('center', 1550)) # 2. CORRIGIDO: Subiu para 1400px (visível e bem posicionado no 1080x1920)
                    .fx(vfx.fadein, 0.1)
                )
                
                txt_clip.fps = 30.0
                legendas.append(txt_clip)
            except Exception as e:
                print(f"⚠️ Erro ao criar legenda '{texto_bloco}': {e}")
                continue

    print(f"✓ {len(legendas)} blocos de legenda gerados.")
    return legendas

def montar_video_v2(
    audio_path: str,
    roteiro_cenas: list,
    pasta_saida: str,
    nome_projeto: str,
    backgrounds_por_bloco: list[str] | None = None,
    musica_path: str | None = None,
    sufixo: str = "",
    musica_volume: float = 0.12
) -> str:

    if not audio_path or not os.path.exists(audio_path):
        raise ValueError(f"Áudio inválido ou não encontrado: {audio_path}")
    
    if backgrounds_por_bloco:
        for i, bg in enumerate(backgrounds_por_bloco):
            if not bg or not os.path.exists(bg):
                raise ValueError(f"Background {i+1} inválido: {bg}")
    
    if musica_path and not os.path.exists(musica_path):
        print(f"⚠️ Música não encontrada: {musica_path} — continuando sem música.")
        musica_path = None
        
    os.makedirs(pasta_saida, exist_ok=True)

    print(f"audio_path: {audio_path}")
    print(f"n cenas: {len(roteiro_cenas)}")
    
    audio_voz = AudioFileClip(audio_path)
    DURACAO_TOTAL = audio_voz.duration
    print(f"DURACAO_TOTAL: {DURACAO_TOTAL}")
    
    duracoes = _calcular_duracoes(roteiro_cenas, DURACAO_TOTAL)
    print(f"duracoes: {duracoes}")

    lista_bgs = listar_backgrounds()
    if not lista_bgs:
        raise FileNotFoundError("Nenhum background encontrado em inputs/videos_fundo/")

    camadas_video   = []
    tempo_acumulado = 0.0

    for idx, cena in enumerate(roteiro_cenas):
        duracao_real = duracoes[idx]

        if backgrounds_por_bloco and idx < len(backgrounds_por_bloco):
            bg_path = backgrounds_por_bloco[idx]
        else:
            bg_path = random.choice(lista_bgs)

        bg = criar_fundo_base(bg_path, duracao_real, tempo_acumulado)
        camadas_video.append(bg)

        if cena["tipo"] == "foco":
            nome_original = cena.get('carta', '')
            if nome_original and nome_original != 'link_na_bio':
                nome_arquivo  = remover_acentos(nome_original).replace(" ", "_")
                caminho_img   = os.path.join(
                    BASE_DIR, "inputs", "cartas", f"{nome_arquivo}.jpg"
                )
                if os.path.exists(caminho_img):
                    img_clip = (
                        ImageClip(caminho_img)
                        .resize(height=900)
                        .set_fps(30)
                        .set_position('center')
                        .set_duration(duracao_real)
                        .set_start(tempo_acumulado)
                        .fx(vfx.fadein, 0.6)
                    )
                    if cena.get("invertida"):
                        img_clip = img_clip.rotate(180)

                    txt_clip = (
                        criar_texto_pil(
                            nome_original.upper().replace("_", " ").replace(" ", "\n"),
                            tamanho_fonte=55
                        )
                        .set_start(tempo_acumulado)
                        .set_duration(duracao_real)
                        .set_position(('center', 200))
                        .fx(vfx.fadein, 0.8)
                    )
                    camadas_video.extend([img_clip, txt_clip])

        elif cena["tipo"] in ("lado_a_lado", "cta_integrado"):
            cartas_raw = cena.get("cartas") or cena.get("carta") or []

            if isinstance(cartas_raw, str):
                cartas_raw = [cartas_raw]
            elif isinstance(cartas_raw, list):
                cartas_raw = [
                    item for sublist in cartas_raw
                    for item in (sublist if isinstance(sublist, list) else [sublist])
                ]

            lista_nomes = [
                n for n in cartas_raw
                if n and isinstance(n, str) and n != 'link_na_bio'
            ]

            if lista_nomes:
                h_carta          = 750
                espacamento      = 50
                y_pos_texto      = 350
                sample_nome      = remover_acentos(lista_nomes[0]).replace(" ", "_")
                sample_path      = os.path.join(
                    BASE_DIR, "inputs", "cartas", f"{sample_nome}.jpg"
                )

                if os.path.exists(sample_path):
                    temp_img             = ImageClip(sample_path).resize(height=h_carta)
                    w_real               = temp_img.w
                    largura_grupo        = w_real * len(lista_nomes) + espacamento * (len(lista_nomes) - 1)
                    x_inicial            = (1080 - largura_grupo) / 2

                    for i, nome_carta in enumerate(lista_nomes):
                        n_arq  = remover_acentos(nome_carta).replace(" ", "_")
                        p_img  = os.path.join(
                            BASE_DIR, "inputs", "cartas", f"{n_arq}.jpg"
                        )
                        if os.path.exists(p_img):
                            x_pos = x_inicial + i * (w_real + espacamento)
                            img_c = (
                                ImageClip(p_img)
                                .resize(height=h_carta)
                                .set_fps(30)
                                .set_position((x_pos, 'center'))
                                .set_duration(duracao_real)
                                .set_start(tempo_acumulado)
                                .fx(vfx.fadein, 0.5 + i * 0.2)
                            )
                            if cena.get("invertida"):
                                img_c = img_c.rotate(180)

                            txt_c = criar_texto_pil(
                                nome_carta.upper().replace("_", " ").replace(" ", "\n"),
                                tamanho_fonte=55
                            )
                            centro_x = x_pos + w_real / 2
                            txt_c = (
                                txt_c
                                .set_start(tempo_acumulado)
                                .set_duration(duracao_real)
                                .set_position((centro_x - txt_c.w / 2, y_pos_texto))
                                .fx(vfx.fadein, 0.7 + i * 0.2)
                            )
                            camadas_video.extend([img_c, txt_c])

        tempo_acumulado += duracao_real

    # ── legendas ─────────────────────────────────────────────────────────────
    legendas = gerar_legendas_pil(audio_path)
    camadas_video.extend(legendas)

    # ── logo ─────────────────────────────────────────────────────────────────
    logo_path = os.path.join(BASE_DIR, "logo_projeto.png")
    if os.path.exists(logo_path):
        logo = (
            ImageClip(logo_path, transparent=True)
            .resize(height=150)
            .set_opacity(0.3)
            .set_duration(DURACAO_TOTAL)
            .set_position(("right", "top"))
        )
        camadas_video.append(logo)

    

    # ── áudio ─────────────────────────────────────────────────────────────────
    audio_final_list = [audio_voz.set_start(0).volumex(1.0)]

    lista_musicas = listar_musicas()
    musica_escolhida = musica_path or  None
    

    if musica_escolhida and os.path.exists(musica_escolhida):
        try:
            bg_music = AudioFileClip(musica_escolhida)
            if bg_music.duration < DURACAO_TOTAL:
                bg_music = afx.audio_loop(bg_music, duration=DURACAO_TOTAL)
            else:
                bg_music = bg_music.set_duration(DURACAO_TOTAL)
            audio_final_list.append(bg_music.volumex(musica_volume).audio_fadeout(2))
        except Exception as e:
            print(f"⚠️ Erro ao carregar música: {e}")

    audio_composto = CompositeAudioClip(audio_final_list)

   
    # Agora o seu CompositeVideoClip vai receber a lista totalmente corrigida:
    video = CompositeVideoClip(camadas_video, size=(1080, 1920))
    video.fps = 30.0
    video = (
        video
        .set_fps(30)
        .set_audio(audio_composto)
        .set_duration(DURACAO_TOTAL)
    )

    caminho_base  = os.path.join(pasta_saida, f"{nome_projeto}{sufixo}")
    caminho_final = f"{caminho_base}.mp4"
    contador = 1

    while os.path.exists(caminho_final):
        caminho_final = f"{caminho_base}_{contador:02d}.mp4"
        contador += 1

    print(f"💾 Salvando: {caminho_final}")
    
    

    video.write_videofile(
        caminho_final,
        fps=30,  
        codec="libx264",
        audio_codec="aac",
        bitrate="6000k",
        threads=8,
        preset="ultrafast",
        logger=None
    )

    video.close()
    audio_voz.close()

    cartas_extraidas = []
    for cena in roteiro_cenas:
        carta = cena.get("carta")
        if carta and isinstance(carta, str) and carta != "link_na_bio":
            cartas_extraidas.append(carta)
        elif isinstance(carta, list):
            cartas_extraidas.extend([c for c in carta if c != "link_na_bio"])
            
        cartas_lista = cena.get("cartas")
        if cartas_lista and isinstance(cartas_lista, list):
            cartas_extraidas.extend([c for c in cartas_lista if isinstance(c, str)])

    # Remove duplicadas mantendo a ordem
    cartas_unicas = list(dict.fromkeys(cartas_extraidas))

    caminho_legenda = os.path.join(pasta_saida, "legenda.txt")
    gerar_arquivo_legenda(
        roteiro_cenas=roteiro_cenas,
        cartas=cartas_unicas,
        caminho_saida_txt=caminho_legenda
    )
    

    return caminho_final