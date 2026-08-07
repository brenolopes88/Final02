import os
import json
from pathlib import Path
from moviepy.editor import VideoFileClip

# Configurações de caminhos
PASTA_BGS = Path("backgrounds") # Altere para o caminho da sua pasta
ARQUIVO_JSON = Path("backgrounds.json")

# Dicionários de tradução para o JSON ficar bonito
TRADUCAO_CAT = {"mis": "místico", "nat": "natureza", "abs": "abstrato", "rom": "romântico"}
TRADUCAO_RITMO = {"l": "lento", "m": "médio", "r": "rápido"}

def gerar_pre_catalogo():
    # Carrega o JSON atual se já existir para não apagar o que você já fez
    if ARQUIVO_JSON.exists():
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            catalogo = json.load(f)
    else:
        catalogo = {}

    # Varre a pasta de vídeos
    formatos_suportados = [".mp4", ".mov", ".mkv"]
    arquivos_video = [f for f in os.listdir(PASTA_BGS) if Path(f).suffix.lower() in formatos_suportados]

    for arquivo in arquivos_video:
        # Se o arquivo já está catalogado, pula para poupar processamento
        if arquivo in catalogo:
            continue
            
        partes = arquivo.split("_")
        
        # Se o arquivo não estiver no padrão de 5 partes, ignora ou cria um padrão genérico
        if len(partes) < 5:
            print(f"⚠️ Arquivo fora do padrão ignorado: {arquivo}")
            continue
            
        cat_prefix, cor_prefix, ritmo_prefix, _, nome_com_extensao = partes[:5]
        nome_exibicao = Path(nome_com_extensao).stem.replace("-", " ").title()
        
        # Pega a duração do vídeo de forma automatizada
        caminho_completo = PASTA_BGS / arquivo
        try:
            with VideoFileClip(str(caminho_completo)) as video:
                duracao = round(video.duration, 2)
        except Exception as e:
            print(f"❌ Erro ao ler duração de {arquivo}: {e}")
            duracao = 0.0

        # Monta os metadados extraídos automaticamente do nome + técnico
        catalogo[arquivo] = {
            "nome_exibicao": nome_exibicao,
            "vibe": TRADUCAO_CAT.get(cat_prefix, "indefinido"),
            "ritmo": TRADUCAO_RITMO.get(ritmo_prefix, "médio"),
            "cor_predominante": cor_prefix,
            "elementos_associados": [], # Você preenche depois no braço ou no Streamlit
            "duracao_segundos": duracao,
            "posicao_texto": "inferior", # Padrão inicial
            "tags": [nome_exibicao.lower()]
        }
        print(f"✅ Catalogado: {arquivo} ({duracao}s)")

    # Salva o arquivo JSON atualizado
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, indent=2, ensure_ascii=False)
    print("\n🔮 Pré-catálogo JSON atualizado com sucesso!")

if __name__ == "__main__":
    gerar_pre_catalogo()