import os
import json
from pathlib import Path
from google import genai
from google.genai import types

ROOT = Path(__file__).parent.parent if "scripts" in str(Path(__file__)) or "studio" in str(Path(__file__)) else Path(__file__).parent
GERADOS_DIR = ROOT / "roteiros" / "gerados"
KNOWLEDGE_PATH = ROOT / "inputs" / "tarot_knowledge.json"
PROMPTS_DIR = ROOT / "inputs" / "prompts"

# O Schema é mantido imutável no código para garantir que nenhuma IA quebre a estrutura de blocos
SCHEMA_ROTEIRO = {
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

def listar_prompts_disponiveis() -> dict[str, dict]:
    """Retorna um dicionário {prompt_id: metadata_do_prompt} para popular o Streamlit."""
    prompts = {}
    if not PROMPTS_DIR.exists():
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        return prompts

    for arquivo in PROMPTS_DIR.glob("*.json"):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            prompt_id = dados.get("id", arquivo.stem)
            prompts[prompt_id] = {
                "arquivo": arquivo.name,
                "nome": dados.get("nome", arquivo.stem),
                "descricao": dados.get("descricao", ""),
                "dados_completos": dados
            }
        except Exception as e:
            print(f"⚠️ Erro ao carregar prompt {arquivo.name}: {e}")
            
    return prompts

def carregar_prompt(prompt_id: str) -> dict:
    """Carrega as configurações de um prompt específico pelo ID."""
    prompts = listar_prompts_disponiveis()
    if prompt_id in prompts:
        return prompts[prompt_id]["dados_completos"]
    
    # Fallback: Se não achar o ID informado, pega o primeiro .json disponível
    for p_info in prompts.values():
        return p_info["dados_completos"]
        
    raise FileNotFoundError(f"Nenhum arquivo de prompt encontrado em {PROMPTS_DIR}")

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

def solicitar_roteiro_v2(
    cartas: list[str], 
    dia_semana: str, 
    data_ddmm: str, 
    periodo: str, 
    prompt_id: str = "oraculo_misterioso_v1",
    save_dir: str | None = None
):
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY ou GOOGLE_API_KEY não configuradas no ambiente.")
    
    client = genai.Client(api_key=api_key)
    
    # Carrega as instruções e configurações do preset selecionado
    preset = carregar_prompt(prompt_id)
    system_instruction = preset.get("system_instruction", "")
    user_template = preset.get("user_prompt_template", "")
    config_model = preset.get("config", {})
    
    definicoes = buscar_definicoes(cartas)
    cartas_txt = ", ".join(cartas)
    
    # Interpola as variáveis no template dinâmico de prompt
    user_prompt = user_template.format(
        cartas_txt=cartas_txt,
        dia_semana=dia_semana,
        data_ddmm=data_ddmm,
        periodo=periodo,
        definicoes=definicoes
    )

    response = client.models.generate_content(
        model=config_model.get("model", "gemini-3.5-flash"),
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=SCHEMA_ROTEIRO,
            temperature=config_model.get("temperature", 0.7)
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
    
    destino = Path(save_dir) if save_dir else GERADOS_DIR
    destino.mkdir(parents=True, exist_ok=True)
    caminho_salvamento = destino / nome_arquivo

    with open(caminho_salvamento, 'w', encoding='utf-8') as f:
        json.dump(dados_roteiro, f, ensure_ascii=False, indent=2)

    return [dados_roteiro]