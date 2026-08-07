import os
import re
import shutil
from pydub import AudioSegment
from pathlib import Path


# -------------------------------------------------------------------
# Pausas por tipo de pontuação (em milissegundos)
# Ajuste aqui para calibrar o ritmo do Oráculo
# -------------------------------------------------------------------
PAUSAS_MS = {
    ',':   0,
    ';':  150,
    ':':  150,
    '!':  400,
    '?':  400,
    '...': 800,   # reticências = pausa longa, mistério
    '.':  400,    # ponto final mais respirado
    '|':  2000,   # pausa manual longa — use no roteiro onde quiser silêncio
}

CHUNK_MINIMO_CHARS = 15
CHUNK_MAXIMO_CHARS = 220

# Pontuação que fecha entonação naturalmente — corte seguro
CORTE_FORTE = {'.', '!', '?', '...', '|'}
# Pontuação que sugere pausa mas não fecha entonação — corte aceitável
CORTE_FRACO = {',', ';', ':'}


def obter_cartas_disponiveis(pasta_imagens="inputs/cartas"):
    """Lê a pasta de cartas e retorna apenas os nomes sem a extensão .jpg"""
    caminho = Path(pasta_imagens)
    if not caminho.exists():
        return []
    
    # Pega todos os arquivos .jpg e remove a extensão .jpg
    cartas = [f.stem for f in caminho.glob("*.jpg")]
    cartas.sort()
    return cartas

def dividir_texto(texto: str) -> list:
    if isinstance(texto, list):
        texto = " ".join(texto)
    texto = texto.replace("\n", " ").strip()

    padrao = r'(\.\.\.|[.,;:!?|])'
    partes = re.split(padrao, texto)

    chunks_brutos = []
    i = 0
    while i < len(partes):
        trecho = partes[i].strip()
        pausa = PAUSAS_MS.get('.', 300)
        marcador = None

        if i + 1 < len(partes) and partes[i + 1].strip() in PAUSAS_MS:
            marcador = partes[i + 1].strip()
            pausa = PAUSAS_MS[marcador]
            i += 2
        else:
            i += 1

        if trecho:
            chunks_brutos.append((trecho, pausa, marcador))

    chunks_finais = []
    buffer_texto = ""
    buffer_pausa = 0

    for texto_chunk, pausa_chunk, marcador in chunks_brutos:
        candidato = (buffer_texto + " " + texto_chunk).strip()

        if buffer_texto and len(candidato) > CHUNK_MAXIMO_CHARS:
            # Só força corte se o buffer atual terminou em pontuação forte
            # Se terminou em pontuação fraca, ainda aceita se não estourar muito
            margem = CHUNK_MAXIMO_CHARS * 1.15  # 15% de tolerância
            if buffer_pausa in [PAUSAS_MS.get(p) for p in CORTE_FORTE] \
               or len(candidato) > margem:
                chunks_finais.append((buffer_texto, buffer_pausa))
                buffer_texto = texto_chunk
                buffer_pausa = pausa_chunk
            else:
                # pontuação fraca e dentro da margem — funde mesmo assim
                buffer_texto = candidato
                buffer_pausa = pausa_chunk
        else:
            buffer_texto = candidato
            buffer_pausa = pausa_chunk

        # Saída antecipada só em pontuação forte para preservar cadência
        if len(buffer_texto) >= CHUNK_MINIMO_CHARS and \
           buffer_pausa in [PAUSAS_MS.get(p) for p in CORTE_FORTE] and \
           len(buffer_texto) >= CHUNK_MAXIMO_CHARS * 0.6:
            chunks_finais.append((buffer_texto, buffer_pausa))
            buffer_texto = ""
            buffer_pausa = 0

    # Flush final
    if buffer_texto:
        if chunks_finais:
            ultimo_texto, ultima_pausa = chunks_finais[-1]
            if len(ultimo_texto) + len(buffer_texto) + 1 <= CHUNK_MAXIMO_CHARS:
                chunks_finais[-1] = (ultimo_texto + " " + buffer_texto, ultima_pausa)
            else:
                chunks_finais.append((buffer_texto, buffer_pausa))
        else:
            chunks_finais.append((buffer_texto, buffer_pausa))

    return chunks_finais


def limpar_pasta_temp(pasta: str = "temp"):
    """Remove todos os arquivos da pasta temporária após cada renderização."""
    if os.path.exists(pasta):
        for arquivo in os.listdir(pasta):
            caminho = os.path.join(pasta, arquivo)
            try:
                if os.path.isfile(caminho):
                    os.remove(caminho)
            except Exception as e:
                print(f"⚠️ Não foi possível remover {caminho}: {e}")

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