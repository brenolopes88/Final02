import csv
import json
import random
import re
import shutil
import unicodedata
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime

from gerador_gemini import solicitar_roteiro
from scripts.video_v2 import montar_video_v2, listar_musicas
from scripts.voz import gerar_audio_oraculo

ROOT = Path(__file__).parent.resolve()
PROJECTS_DIR = ROOT / "projects"
PRESETS_PATH = ROOT / "scripts" / "presets_voz.json"
DEFAULT_CSV = ROOT / "flow.csv"

FIELD_ALIASES = {
    "data": ["data", "date", "dia", "day"],
    "cartas": ["cartas", "cards", "carta", "card"],
    "humor": ["humor", "mood", "tom", "preset", "voz"],
    "periodo": ["periodo", "period", "turno", "manh", "noite"]
}

HUMOR_ALIASES = {
    "padrao": "Padrão",
    "padrão": "Padrão",
    "default": "Padrão",
    "normal": "Padrão",
    "solene": "Solene",
    "intenso": "Intenso",
    "meditativo": "Meditativo",
    "meditacao": "Meditativo",
    "meditação": "Meditativo",
    "meditative": "Meditativo"
}

PERIODO_ALIASES = {
    "manha": "MANHÃ",
    "manhã": "MANHÃ",
    "m": "MANHÃ",
    "noite": "NOITE",
    "n": "NOITE",
    "night": "NOITE"
}

def normalize_text(value: str) -> str:
    value = str(value or "")
    value = unicodedata.normalize("NFD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()

def slugify(value: str) -> str:
    value = str(value or "")
    value = unicodedata.normalize("NFD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^0-9a-zA-Z]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "texto"

def load_presets() -> dict:
    if PRESETS_PATH.exists():
        try:
            return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "Padrão": {"temperatura": 0.88, "velocidade": 1.12},
        "Solene": {"temperatura": 0.70, "velocidade": 0.95},
        "Intenso": {"temperatura": 0.95, "velocidade": 1.20},
        "Meditativo": {"temperatura": 0.75, "velocidade": 0.90},
    }

PRESETS = load_presets()
NORMALIZED_HUMORS = {normalize_text(k): k for k in PRESETS}
NORMALIZED_HUMORS.update(HUMOR_ALIASES)

def detect_delimiter(text: str) -> str:
    try:
        sample = "\n".join(text.splitlines()[:10])
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        return dialect.delimiter
    except csv.Error:
        return ","

def normalize_header(header: str) -> str:
    header = normalize_text(header or "")
    for canonical, variants in FIELD_ALIASES.items():
        if header in [normalize_text(v) for v in variants]:
            return canonical
    return header

def parse_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        return []

    delimiter = detect_delimiter("\n".join(lines[:10]))
    reader = csv.reader(lines, delimiter=delimiter)
    rows = []
    first = next(reader, None)
    if not first:
        return []

    headers = [normalize_header(col) for col in first]
    required = {"data", "cartas", "humor"}
    has_header = required.issubset(set(headers))

    if has_header:
        reader = csv.DictReader(lines, delimiter=delimiter)
        for row in reader:
            normalized = {"data": None, "cartas": None, "humor": None, "periodo": None}
            for key, value in row.items():
                if key is None:
                    continue
                canon = normalize_header(key)
                if canon in normalized:
                    normalized[canon] = value
            rows.append(normalized)
    else:
        reader = csv.reader(lines, delimiter=delimiter)
        for row in reader:
            if len(row) >= 3:
                rows.append({
                    "data": row[0],
                    "cartas": row[1],
                    "humor": row[2],
                    "periodo": row[3] if len(row) > 3 else None,
                })
    return rows

def parse_date(value: str) -> str | None:
    if not value:
        return None
    value = value.strip()
    patterns = [
        r"^(\d{1,2})[\/\-](\d{1,2})$",
        r"^(\d{2})(\d{2})$",
        r"^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if not match:
            continue
        if pattern == patterns[0] or pattern == patterns[1]:
            d, m = match.groups()
        else:
            _, m, d = match.groups()
        try:
            day = int(d)
            month = int(m)
            if 1 <= day <= 31 and 1 <= month <= 12:
                return f"{day:02d}-{month:02d}"
        except ValueError:
            return None
    return None

def normalize_period(value: str | None, cards: list[str]) -> str:
    if value:
        token = normalize_text(value)
        if token in PERIODO_ALIASES:
            return PERIODO_ALIASES[token]
        if token.startswith("m"):
            return "MANHÃ"
        if token.startswith("n"):
            return "NOITE"
    return "MANHÃ" if len(cards) == 1 else "NOITE"

def normalize_humor(value: str | None) -> str:
    if not value:
        return "Padrão"
    normalized = normalize_text(value)
    if normalized in NORMALIZED_HUMORS:
        return NORMALIZED_HUMORS[normalized]
    return "Padrão"

def split_cards(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,;|]+", value)
    return [part.strip() for part in parts if part.strip()]

def normalize_row(raw_row: dict, row_number: int) -> dict | None:
    data_raw = str(raw_row.get("data") or "").strip()
    cards_raw = str(raw_row.get("cartas") or "").strip()
    humor_raw = str(raw_row.get("humor") or "").strip()
    periodo_raw = str(raw_row.get("periodo") or "").strip()

    date = parse_date(data_raw)
    if not date:
        print(f"[WARN] Linha {row_number}: data inválida '{data_raw}'. Pulando.")
        return None

    cards = split_cards(cards_raw)
    if not cards:
        print(f"[WARN] Linha {row_number}: cartas vazias. Pulando.")
        return None

    if len(cards) > 2:
        print(f"[WARN] Linha {row_number}: mais de 2 cartas informadas. Usando apenas as duas primeiras.")
        cards = cards[:2]

    periodo = normalize_period(periodo_raw, cards)
    humor = normalize_humor(humor_raw)
    preset = PRESETS.get(humor, PRESETS.get("Padrão"))

    if humor not in PRESETS:
        print(f"[WARN] Linha {row_number}: humor '{humor_raw}' não reconhecido. Usando 'Padrão'.")
        humor = "Padrão"

    period_code = "M" if periodo == "MANHÃ" else "N"
    card_slug = "_".join(slugify(c) for c in cards)
    base_name = f"{date}-{period_code}"
    project_name = f"{base_name}_{card_slug}" if card_slug else base_name

    return {
        "date": date,
        "cards": cards,
        "humor": humor,
        "preset": preset,
        "periodo": periodo,
        "period_code": period_code,
        "project_name": project_name,
        "raw": raw_row,
    }

def unique_project_path(name: str) -> Path:
    candidate = PROJECTS_DIR / name
    suffix = 1
    while candidate.exists():
        candidate = PROJECTS_DIR / f"{name}_{suffix:02d}"
        suffix += 1
    return candidate

def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def process_row(entry: dict, dry_run: bool = False) -> bool:
    project_path = unique_project_path(entry["project_name"])
    print(f"\n=== Processando: {project_path.name} ===")
    print(f"  data    : {entry['date']}")
    print(f"  cartas  : {entry['cards']}")
    print(f"  humor   : {entry['humor']}")
    print(f"  periodo : {entry['periodo']}")

    if dry_run:
        print("  [dry-run] pulando geração.")
        return True

    project_path.mkdir(parents=True, exist_ok=True)

    data_obj = datetime.strptime(entry["date"], "%d-%m")
    dia_semana = data_obj.strftime("%A").upper()
    DIAS_PT = {
        "MONDAY": "SEGUNDA", "TUESDAY": "TERÇA", "WEDNESDAY": "QUARTA",
        "THURSDAY": "QUINTA", "FRIDAY": "SEXTA", "SATURDAY": "SÁBADO", "SUNDAY": "DOMINGO"
    }
    dia_semana_pt = DIAS_PT.get(dia_semana, "SEGUNDA")

    try:
        roteiro = solicitar_roteiro(
            cartas=entry["cards"],
            dia_semana=dia_semana_pt,
            data_ddmm=entry["date"],
            periodo=entry["periodo"],
            save_dir=str(project_path),
        )
    except Exception as exc:
        print(f"[ERROR] Falha ao gerar roteiro: {exc}")
        return False

    if not roteiro or not isinstance(roteiro, list) or not roteiro[0].get("roteiro"):
        print("[ERROR] Roteiro inválido ou vazio.")
        return False

    roteiro_data = roteiro[0]
    print(f"  ✓ Roteiro salvo em {project_path / 'roteiro.json'}")

    try:
        text_blocks = [bloco.get("texto", "") for bloco in roteiro_data.get("roteiro", [])]
        audio_path = gerar_audio_oraculo(
            texto=text_blocks,
            nome_projeto=project_path.name,
            temperature=float(entry["preset"]["temperatura"]),
            speed=float(entry["preset"]["velocidade"]),
            output_dir=str(project_path),
        )
    except Exception as exc:
        print(f"[ERROR] Falha ao gerar voz: {exc}")
        return False

    if not audio_path or not Path(audio_path).exists():
        print(f"[ERROR] Arquivo de voz não encontrado após geração: {audio_path}")
        return False

    voice_target = project_path / "voz.wav"
    src = Path(audio_path)
    try:
        if src.resolve() != voice_target.resolve():
            src.replace(voice_target)
    except Exception:
        shutil.copy2(str(src), str(voice_target))
    print(f"  ✓ Voz disponível em {voice_target}")

    # Seleção de Música Pure Random
    musica = random.choice(listar_musicas()) if listar_musicas() else None
    if musica:
        print(f"  ✓ Música selecionada (aleatória): {Path(musica).name}")
    else:
        print("  ⚠️ Nenhuma música encontrada. O vídeo será gerado sem trilha sonora.")

    try:
        video_path = montar_video_v2(
            audio_path=str(voice_target),
            roteiro_cenas=roteiro_data.get("roteiro", []),
            pasta_saida=str(project_path),
            nome_projeto=project_path.name,
            backgrounds_por_bloco=None, # None força o montar_video_v2 a usar vídeos aleatórios
            musica_path=musica,
            musica_volume=0.12,
        )
    except Exception as exc:
        print(f"[ERROR] Falha ao montar vídeo: {exc}")
        return False

    print(f"  ✓ Vídeo final salvo em {video_path}")
    return True

def process_existing_roteiro(roteiro_data: dict, humor: str, date: str | None = None, cards: list | None = None, dry_run: bool = False) -> bool:
    """Processa um roteiro JSON já existente: salva no projeto, gera voz e monta vídeo com assets aleatórios."""
    roteiro_root = None
    if isinstance(roteiro_data, list):
        if len(roteiro_data) == 0:
            print("[ERROR] Roteiro vazio fornecido.")
            return False
        first = roteiro_data[0]
        if isinstance(first, dict) and "roteiro" in first:
            roteiro_root = first
        elif all(isinstance(item, dict) for item in roteiro_data):
            roteiro_root = {"id": "imported", "roteiro": roteiro_data}
        else:
            print("[ERROR] Formato de roteiro não reconhecido.")
            return False
    elif isinstance(roteiro_data, dict):
        if "roteiro" in roteiro_data:
            roteiro_root = roteiro_data
        else:
            if all(isinstance(v, dict) for v in roteiro_data.values()):
                cenas = list(roteiro_data.values())
                roteiro_root = {"id": "imported", "roteiro": cenas}
            else:
                print("[ERROR] Roteiro dict sem chave 'roteiro' e formato inesperado.")
                return False
    else:
        print("[ERROR] Tipo de dado do roteiro inválido.")
        return False

    if not cards:
        cartas_extraidas = []
        for cena in roteiro_root.get("roteiro", []):
            carta = cena.get("carta")
            if carta and isinstance(carta, str) and carta != "link_na_bio":
                cartas_extraidas.append(carta)
            elif isinstance(carta, list):
                cartas_extraidas.extend([c for c in carta if c != "link_na_bio"])
            cartas_lista = cena.get("cartas")
            if cartas_lista and isinstance(cartas_lista, list):
                cartas_extraidas.extend([c for c in cartas_lista if isinstance(c, str)])
        cards = list(dict.fromkeys(cartas_extraidas))

    date_str = parse_date(date) if date else None
    if not date_str:
        date_str = "00-00"

    periodo = normalize_period(None, cards)
    period_code = "M" if periodo == "MANHÃ" else "N"
    card_slug = "_".join(slugify(c) for c in (cards or [])[:2])
    base_name = f"{date_str}-{period_code}"
    project_name = f"{base_name}_{card_slug}" if card_slug else base_name

    project_path = unique_project_path(project_name)
    print(f"\n=== Processando (roteiro existente): {project_path.name} ===")
    print(f"  data    : {date_str}")
    print(f"  cartas  : {cards}")
    print(f"  humor   : {humor}")

    if dry_run:
        print("  [dry-run] pulando geração.")
        return True

    project_path.mkdir(parents=True, exist_ok=True)

    save_json(project_path / "roteiro.json", roteiro_root)
    print(f"  ✓ Roteiro salvo em {project_path / 'roteiro.json'}")

    # Usa o preset do humor apenas para controlar o tom/ritmo da Voz
    preset = PRESETS.get(humor, PRESETS.get("Padrão"))
    try:
        text_blocks = [bloco.get("texto", "") for bloco in roteiro_root.get("roteiro", [])]
        audio_path = gerar_audio_oraculo(
            texto=text_blocks,
            nome_projeto=project_path.name,
            temperature=float(preset["temperatura"]),
            speed=float(preset["velocidade"]),
            output_dir=str(project_path),
        )
    except Exception as exc:
        print(f"[ERROR] Falha ao gerar voz: {exc}")
        return False

    if not audio_path or not Path(audio_path).exists():
        print(f"[ERROR] Arquivo de voz não encontrado após geração: {audio_path}")
        return False

    voice_target = project_path / "voz.wav"
    src = Path(audio_path)
    try:
        if src.resolve() != voice_target.resolve():
            src.replace(voice_target)
    except Exception:
        shutil.copy2(str(src), str(voice_target))
    print(f"  ✓ Voz disponível em {voice_target}")

    # Música totalmente aleatória
    musica = random.choice(listar_musicas()) if listar_musicas() else None
    if musica:
        print(f"  ✓ Música selecionada (aleatória): {Path(musica).name}")
    else:
        print("  ⚠️ Nenhuma música encontrada. O vídeo será gerado sem trilha sonora.")

    try:
        video_path = montar_video_v2(
            audio_path=str(voice_target),
            roteiro_cenas=roteiro_root.get("roteiro", []),
            pasta_saida=str(project_path),
            nome_projeto=project_path.name,
            backgrounds_por_bloco=None, # Usará seleção aleatória interna
            musica_path=musica,
            musica_volume=0.12,
        )
    except Exception as exc:
        print(f"[ERROR] Falha ao montar vídeo: {exc}")
        return False

    print(f"  ✓ Vídeo final salvo em {video_path}")
    return True

def print_csv_instructions() -> None:
    print("\nUse um arquivo CSV chamado 'flow.csv' no root com colunas:\n")
    print("  data,cartas,humor")
    print("Exemplo:")
    print("  28/07,Imperatriz,Padrão")
    print("  29/07,Dois de Copas;A Estrela,Intenso")
    print("  30/07,O Eremita,Meditativo")
    print("\nRegras: 1 carta = período MANHÃ; 2 cartas = período NOITE.")

def main() -> None:
    parser = ArgumentParser(
        description="Processo direto de flow.csv -> roteiro + voz + vídeo + legenda"
    )
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Caminho para o CSV de entrada")
    parser.add_argument("--dry-run", action="store_true", help="Valida o CSV sem gerar artefatos")
    parser.add_argument("--sample", action="store_true", help="Cria um arquivo sample_flow.csv com formato recomendado")
    args = parser.parse_args()

    if args.sample:
        sample_path = ROOT / "flow_sample.csv"
        if sample_path.exists():
            print(f"Arquivo de exemplo já existe em: {sample_path}")
            return
        sample_path.write_text(
            "data,cartas,humor\n"
            "28/07,Imperatriz,Padrão\n"
            "29/07,Dois de Copas;A Estrela,Intenso\n"
            "30/07,O Eremita,Meditativo\n",
            encoding="utf-8",
        )
        print(f"Arquivo de exemplo criado em: {sample_path}")
        return

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Arquivo CSV não encontrado: {csv_path}")
        print_csv_instructions()
        return

    rows = parse_csv(csv_path)
    if not rows:
        print("Nenhuma linha válida encontrada no CSV.")
        print_csv_instructions()
        return

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    parsed = []
    duplicates = {}
    for index, raw_row in enumerate(rows, start=1):
        entry = normalize_row(raw_row, index)
        if not entry:
            continue
        key = (entry["date"], entry["period_code"])
        duplicates.setdefault(key, 0)
        duplicates[key] += 1
        parsed.append(entry)

    for (date, period), count in duplicates.items():
        if count > 1:
            print(f"[WARN] Existem {count} linhas com a mesma data/período: {date}-{period}.")

    success = 0
    for entry in parsed:
        if process_row(entry, dry_run=args.dry_run):
            success += 1

    print(f"\nProcessamento concluído: {success} de {len(parsed)} entradas geradas com sucesso.")

if __name__ == "__main__":
    main()