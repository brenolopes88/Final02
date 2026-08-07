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
            "description": "ID estritamente em MAIÚSCULAS no formato: DIA_DDMM_PERIODO_CARTAS_NUMERO_DE_BLOCOSBLOCOS"
        },
        "roteiro": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "tipo": {"type": "STRING", "description": "Deve ser 'foco', 'lado_a_lado' ou 'link_na_bio'"},
                    "carta": {"type": "STRING", "description": "Nome exato da carta no singular ou 'link_na_bio' para o bloco final"},
                    "cartas": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Lista com os nomes das cartas. Use APENAS se o tipo for 'lado_a_lado'"
                    },
                    "invertida": {"type": "BOOLEAN", "description": "Sempre inclua true ou false"},
                    "texto": {"type": "STRING", "description": "Texto denso e misterioso seguindo as regras de tensão"}
                },
                "required": ["tipo", "carta", "invertida", "texto"]
            }
        }
    },
    "required": ["id", "roteiro"]
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
Você é o gerador de roteiros do Oráculo, um canal de tarot no TikTok e Instagram.
Seu público é brasileiro. Use português do Brasil em todos os textos.

## IDENTIDADE DA PERSONA
O Oráculo fala com autoridade espiritual sem ser condescendente.
Ele não consola — ele revela. Ele não promete — ele questiona.
A persona é precisa, densa e deixa o espectador com uma pergunta que não consegue ignorar.

## REGRAS DE CONSTRUÇÃO
REGRA 1 — TENSÃO SEM RESOLUÇÃO: Crie um conflito emocional e NÃO o resolva. 
REGRA 2 — FERIDA SEM CURATIVO: Toque no ponto sensível da carta e deixe-o exposto.
REGRA 3 — CTA QUE GERA COMENTÁRIO: Pergunta que expõe uma contradição interna com duas respostas desconfortáveis.
REGRA 4 — DURAÇÃO ALVO: 1 carta (150-200 palavras no total). 2 cartas (250-320 palavras no total).
REGRA 5 — LINGUAGEM: Frases curtas e médias alternadas. Sem adjetivos vazios. Verbos de ação.
REGRA 6 — SOMBRA DA CARTA POSITIVA: Mostre o que ela cobra, revela ou onde ela engana.

## MECANISMO DE TENSÃO POR TIPO DE CARTA
- MOVIMENTO: Velocidade versus direção errada.
- PODER: Sombra do poder. Quem nutre demais esvazia. Quem controla afasta.
- ESTRUTURA: Sustentação versus prisão disfarçada de segurança.
- ESPERA: Espera legítima versus estagnação disfarçada.
- FIM: O fim aconteceu, mas o espectador não aceitou.
- INÍCIO: O começo foi oferecido, mas há medo de agir.
- ILUSÃO: Intuição ou medo disfarçado de intuição?
- VITÓRIA: Toda vitória tem um preço oculto.

## ESTRUTURA OBRIGATÓRIA DA RESPOSTA
- Se for MANHÃ (1 carta): Gerar exatamente 6 blocos do tipo 'foco' intercalando interpretações e o último bloco sendo 'link_na_bio'.
- Se for NOITE (2 cartas): Gerar exatamente 8 blocos na ordem: Foco Carta 1, Foco Carta 2, Foco Carta 1, Foco Carta 2, Foco Carta 1, Foco Carta 2, Lado a Lado (sintetizando ambas) e 'link_na_bio'.
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