import os
import json
from pathlib import Path
from google import genai
from google.genai import types

ROOT = Path(__file__).parent.parent if "scripts" in str(Path(__file__)) or "studio" in str(Path(__file__)) else Path(__file__).parent
GERADOS_DIR = ROOT / "roteiros" / "gerados"
KNOWLEDGE_PATH = ROOT / "inputs" / "tarot_knowledge.json"

schema_roteiro = {
    "type": "OBJECT",
    "properties": {
        "id": {
            "type": "STRING",
            "description": (
                "ID estritamente em MAIÚSCULAS no formato:"
                " DIA_DDMM_PERIODO_CARTAS_NUMERO_DE_BLOCOS"
            ),
        },
        "roteiro": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "tipo": {
                        "type": "STRING",
                        "description": (
                            "Deve ser 'foco', 'lado_a_lado' ou 'link_na_bio'"
                        ),
                    },
                    "carta": {
                        "type": "STRING",
                        "description": (
                            "Nome exato da carta no singular ou 'link_na_bio'"
                            " para o bloco final"
                        ),
                    },
                    "cartas": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": (
                            "Lista com os nomes das cartas. Use APENAS se o"
                            " tipo for 'lado_a_lado'"
                        ),
                    },
                    "invertida": {
                        "type": "BOOLEAN",
                        "description": "Sempre inclua true ou false",
                    },
                    "texto": {
                        "type": "STRING",
                        "description": (
                            "Texto extremamente curto, direto, denso e"
                            " misterioso"
                        ),
                    },
                },
                "required": ["tipo", "carta", "invertida", "texto"],
            },
        },
    },
    "required": ["id", "roteiro"],
}

def buscar_definicoes(cartas: list[str]) -> str:
    if not KNOWLEDGE_PATH.exists():
        return ""
    try:
        with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
            knowledge = json.load(f)
    except Exception:
        return ""

    linhas = ["## DEFINIÇÕES DAS CARTAS DESTE ROTEIRO\n"]
    for carta in cartas:
        carta_lower = carta.lower().strip()
        dados = knowledge.get(carta_lower)
        if not dados:
            for nome, info in knowledge.items():
                if carta_lower in nome or nome in carta_lower:
                    dados = info
                    break
        if dados:
            linhas.append(f"### {dados.get('name', carta)}")
            linhas.append(f"**Essência:** {dados.get('essence', '')}")
            linhas.append(f"**Luz:** {dados.get('lightMeaning', '')}")
            linhas.append(f"**Sombra:** {dados.get('shadowMeaning', '')}")
            linhas.append(f"**Conselho:** {dados.get('guidanceWhenReversed', '')}")
            linhas.append("")
    return "\n".join(linhas)

SYSTEM_PROMPT = """
Você é o gerador de roteiros do Oráculo, um canal de tarot e espiritualidade no TikTok e Instagram.
Seu público é brasileiro. Use português do Brasil em todos os textos.

## IDENTIDADE DA PERSONA
O Oráculo fala com autoridade espiritual sem ser condescendente.
Ele não consola — ele revela. Ele não promete — ele questiona.
A persona é precisa, densa e deixa o espectador com uma pergunta que não consegue ignorar.

## REGRAS RÍGIDAS DE CONSTRUÇÃO E TAMANHO
REGRA 1 — LIMITE EXTREMO DE PALAVRAS (DURAÇÃO ALVO: 35 A 45 SEGUNDOS):
  - Se for MANHÃ (1 carta): O ROTEIRO COMPLETO deve ter entre 80 e 95 PALAVRAS NO TOTAL (soma de todos os blocos).
  - Se for NOITE (2 cartas): O ROTEIRO COMPLETO deve ter entre 90 e 105 PALAVRAS NO TOTAL (soma de todos os blocos).
  NÃO EXCEDA ESSES LIMITES SOB HIPÓTESE ALGUMA. FRASES CURTAS E DIRETAS.

REGRA 2 — BLOCO 1 É UM GANCHO DE IMPACTO (0 a 3 segundos):
  O primeiro bloco NUNCA deve citar o nome da carta, nem saudações como "Bom dia" ou "A noite traz".
  O Bloco 1 deve SER UMA AFIRMAÇÃO IMPACTANTE ou PROVOCAÇÃO PSICOLÓGICA DIRETA que exponha uma ferida ou contradição imediata.

REGRA 3 — TENSÃO SEM RESOLUÇÃO: Crie um conflito emocional e NÃO o resolva. Exponha a ferida e deixe-a aberta.

REGRA 4 — CTA FOCADA NO APP ORÁCULO E ENGAJAMENTO (Último bloco - 'link_na_bio'):
  Faça uma pergunta de contradição interna que force um comentário E convide a ver o ritual no App Oráculo.
  Exemplo: "Você prefere encarar essa verdade ou continuar se enganando? Baixe o App Oráculo na bio para ver o seu I Ching de hoje e comente 'LUCIDEZ' para selar."

REGRA 5 — SOMBRA DA CARTA: Mostre o que a carta cobra, revela ou onde ela engana.

## MECANISMO DE TENSÃO POR TIPO DE CARTA
- MOVIMENTO: Velocidade versus direção errada.
- PODER: Sombra do poder. Quem nutre demais esvazia.
- ESTRUTURA: Sustentação versus prisão disfarçada de segurança.
- ESPERA: Espera legítima versus estagnação disfarçada.
- FIM: O fim aconteceu, mas você finge que não vê.
- INÍCIO: O começo foi oferecido, mas o medo de agir te paralisa.

## ESTRUTURA OBRIGATÓRIA DA RESPOSTA (RESPEITE OS BLOCOS):
- MANHÃ (1 carta): Gerar exatamente 4 blocos curtos:
  Bloco 1 (foco): Gancho de impacto psicológico (sem citar nome da carta).
  Bloco 2 (foco): A revelação e a sombra da carta no dia.
  Bloco 3 (foco): O confronto emocional / a cobrança da carta.
  Bloco 4 (link_na_bio): A pergunta de contradição + chamada para o App Oráculo na bio.

- NOITE (2 cartas): Gerar exatamente 5 blocos curtos:
  Bloco 1 (foco): Gancho de impacto unindo o conflito noturno.
  Bloco 2 (foco): Síntese da Carta 1.
  Bloco 3 (foco): Síntese da Carta 2.
  Bloco 4 (lado_a_lado): O choque/conflito entre as duas cartas.
  Bloco 5 (link_na_bio): A pergunta de contradição + chamada para o App Oráculo na bio.
"""

def solicitar_roteiro(cartas: list[str], dia_semana: str, data_ddmm: str, periodo: str, save_dir: str | None = None):
    # Load API key from environment. Do NOT keep secrets in source code.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Export GEMINI_API_KEY or set GOOGLE_API_KEY in your environment."
        )
    client = genai.Client(api_key=api_key)
    
    definicoes = buscar_definicoes(cartas)
    cartas_txt = ", ".join(cartas)
    
    user_prompt = f"""
    Gere um roteiro para as seguintes cartas: {cartas_txt}
    Dia da Semana: {dia_semana}
    Data: {data_ddmm}
    Período: {periodo}

    {definicoes}

    INSTRUÇÕES ESPECÍFICAS DE BLOCO:
    Respeite o número de blocos determinado para o período de {periodo} conforme as regras do sistema.
    Fale sempre diretamente com 'você'. Exponha a ferida sem curar. Não console.
    No bloco de CTA (link_na_bio), faça uma pergunta de contradição interna que termine com '?'.
    """

    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=schema_roteiro,
            temperature=0.7
        ),
    )
    
    dados_roteiro = json.loads(response.text)
    
    sufixo_arquivo = "M" if periodo.upper() in ["MANHÃ", "MANHA"] else "N"
    data_limpa = data_ddmm.replace("/", "").replace("-", "")
    if len(data_limpa) == 4:
        data_formatada = f"{data_limpa[:2]}-{data_limpa[2:]}"
    else:
        data_formatada = data_ddmm.replace("/", "-")
        
    nome_arquivo = f"{data_formatada}-{sufixo_arquivo}.json"
    
    # Decide onde salvar: se save_dir foi fornecido, salva lá; caso contrário usa a pasta padrão
    if save_dir:
        destino = Path(save_dir)
    else:
        destino = GERADOS_DIR

    destino.mkdir(parents=True, exist_ok=True)
    caminho_salvamento = destino / nome_arquivo

    with open(caminho_salvamento, 'w', encoding='utf-8') as f:
        json.dump(dados_roteiro, f, ensure_ascii=False, indent=2)

    return [dados_roteiro]