# scripts/build_knowledge.py
# Roda uma vez para converter os .kt em JSON consultável pelo gerador
import re
import json
import os

def extrair_cartas_kt(caminho: str) -> list[dict]:
    with open(caminho, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    cartas = []

    # extrai cada bloco TarotCard(...)
    blocos = re.findall(
        r'TarotCard\s*\((.*?)\n\s*\)',
        conteudo,
        re.DOTALL
    )

    for bloco in blocos:
        carta = {}

        # name
        m = re.search(r'name\s*=\s*"([^"]+)"', bloco)
        if m:
            carta['name'] = m.group(1)

        # essence
        m = re.search(r'essence\s*=\s*"""(.*?)"""', bloco, re.DOTALL)
        if m:
            carta['essence'] = m.group(1).strip()
        else:
            m = re.search(r'essence\s*=\s*"([^"]+)"', bloco)
            if m:
                carta['essence'] = m.group(1)

        # lightMeaning
        m = re.search(r'lightMeaning\s*=\s*"""(.*?)"""', bloco, re.DOTALL)
        if m:
            carta['lightMeaning'] = m.group(1).strip()
        else:
            m = re.search(r'lightMeaning\s*=\s*"([^"]+)"', bloco)
            if m:
                carta['lightMeaning'] = m.group(1)

        # shadowMeaning
        m = re.search(r'shadowMeaning\s*=\s*"""(.*?)"""', bloco, re.DOTALL)
        if m:
            carta['shadowMeaning'] = m.group(1).strip()
        else:
            m = re.search(r'shadowMeaning\s*=\s*"([^"]+)"', bloco)
            if m:
                carta['shadowMeaning'] = m.group(1)

        # guidanceWhenReversed
        m = re.search(r'guidanceWhenReversed\s*=\s*"""(.*?)"""', bloco, re.DOTALL)
        if m:
            carta['guidanceWhenReversed'] = m.group(1).strip()
        else:
            m = re.search(r'guidanceWhenReversed\s*=\s*"([^"]+)"', bloco)
            if m:
                carta['guidanceWhenReversed'] = m.group(1)

        # keywordsLight
        m = re.search(r'keywordsLight\s*=\s*listOf\((.*?)\)', bloco, re.DOTALL)
        if m:
            carta['keywordsLight'] = re.findall(r'"([^"]+)"', m.group(1))

        # keywordsShadow
        m = re.search(r'keywordsShadow\s*=\s*listOf\((.*?)\)', bloco, re.DOTALL)
        if m:
            carta['keywordsShadow'] = re.findall(r'"([^"]+)"', m.group(1))

        if carta.get('name'):
            cartas.append(carta)

    return cartas


def build_knowledge():
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # pasta onde estão os .kt — ajusta o caminho se necessário
    kt_dir = os.path.join(ROOT, "inputs", "cards")

    arquivos_kt = [
        "MajorArcana.kt",
        "Wands.kt",
        "Cups.kt",
        "Swords.kt",
        "Pentacles.kt",
    ]

    todas_cartas = []
    for nome in arquivos_kt:
        caminho = os.path.join(kt_dir, nome)
        if os.path.exists(caminho):
            cartas = extrair_cartas_kt(caminho)
            todas_cartas.extend(cartas)
            print(f"✓ {nome}: {len(cartas)} cartas extraídas")
        else:
            print(f"⚠️ Não encontrado: {caminho}")

    # índice por nome para busca rápida
    indice = {carta['name'].lower(): carta for carta in todas_cartas}

    saida = os.path.join(ROOT, "inputs", "tarot_knowledge.json")
    with open(saida, 'w', encoding='utf-8') as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(todas_cartas)} cartas salvas em {saida}")


if __name__ == "__main__":
    build_knowledge()