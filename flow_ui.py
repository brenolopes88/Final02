import json
from pathlib import Path

import streamlit as st

from scripts.utils import obter_cartas_disponiveis
import flow

ROOT = Path(__file__).parent.resolve()
PRESETS_PATH = ROOT / "scripts" / "presets_voz.json"
CARDS_PATH = ROOT / "inputs" / "cartas"


def load_presets() -> dict:
    if PRESETS_PATH.exists():
        try:
            return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return flow.load_presets()


def main() -> None:
    st.set_page_config(page_title="Flow Oráculo", layout="centered")
    st.title("Flow Oráculo — UI Simples")
    st.markdown(
        "Use esta interface para gerar um vídeo direto a partir de: data, cartas e humor. "
        "O arquivo `flow.py` permanece para execução em lote via CSV."
    )

    cards = obter_cartas_disponiveis(CARDS_PATH)
    presets = load_presets()
    humor_options = list(presets.keys())

    if not cards:
        st.warning(
            "Nenhuma carta encontrada em `inputs/cartas/`. Coloque imagens .jpg com nomes de cartas neste diretório."
        )

    modo = st.radio("Modo", ["Novo roteiro", "Roteiro existente"], index=0)

    with st.form("flow_form"):
        if modo == "Novo roteiro":
            col1, col2 = st.columns([1, 1])
            with col1:
                date = st.text_input("Data (DD/MM)", value="28/07")
                humor = st.selectbox("Humor", humor_options)
            with col2:
                selected_cards = st.multiselect(
                    "Cartas (1 ou 2)",
                    options=cards,
                    help="Selecione uma ou duas cartas para o roteiro.",
                )

            if len(selected_cards) > 2:
                st.error("Escolha no máximo duas cartas.")

            submitted = st.form_submit_button("Gerar vídeo")
        else:
            st.write("Envie um arquivo JSON de roteiro ou selecione do explorador.")
            uploaded = st.file_uploader("Roteiro JSON", type=["json"])
            col1, col2 = st.columns([1, 1])
            with col1:
                date = st.text_input("Data (opcional DD/MM)")
                humor = st.selectbox("Humor", humor_options)
            with col2:
                selected_cards = st.multiselect("Cartas (opcional)", options=cards)

            submitted = st.form_submit_button("Gerar vídeo a partir do roteiro")

        if submitted:
            if modo == "Novo roteiro":
                if not date:
                    st.error("Informe uma data válida.")
                    return
                if not selected_cards:
                    st.error("Selecione ao menos uma carta.")
                    return
                if len(selected_cards) > 2:
                    st.error("Selecione no máximo duas cartas.")
                    return

                raw_row = {
                    "data": date,
                    "cartas": ";".join(selected_cards),
                    "humor": humor,
                }
                entry = flow.normalize_row(raw_row, 1)
                if not entry:
                    st.error("Não foi possível normalizar os dados. Verifique o formato e tente novamente.")
                    return

                st.info(f"Gerando projeto: {entry['project_name']}")
                with st.spinner("Processando... isso pode levar alguns minutos"):
                    success = flow.process_row(entry)

            else:
                if not uploaded:
                    st.error("Envie um arquivo JSON válido de roteiro.")
                    return
                try:
                    import json as _json
                    roteiro_data = _json.loads(uploaded.getvalue().decode("utf-8"))
                except Exception as e:
                    st.error(f"Arquivo inválido: {e}")
                    return

                st.info("Gerando projeto a partir do roteiro enviado...")
                with st.spinner("Processando... isso pode levar alguns minutos"):
                    success = flow.process_existing_roteiro(
                        roteiro_data=roteiro_data,
                        humor=humor,
                        date=date or None,
                        cards=selected_cards or None,
                    )

            if success:
                st.success("Vídeo gerado com sucesso!")
                st.markdown(
                    f"Pasta do projeto: `projects/` (verifique a saída no terminal para o nome exato)"
                )
                st.markdown("Veja a pasta do projeto em `projects/` para os arquivos gerados.")
            else:
                st.error("Ocorreu um erro durante a geração. Veja o terminal para mais detalhes.")

    st.markdown("---")
    st.markdown("### Detalhes do fluxo")
    st.markdown(
        "- `data`: formato `DD/MM`, `DD-MM` ou `DDMM`\n"
        "- `cartas`: selecione uma ou duas cartas; 1 carta gera período MANHÃ, 2 cartas gera NOITE\n"
        "- `humor`: seleciona o preset de voz usado na geração" 
    )
    st.markdown("\nSe quiser, use também o `flow.py` para processar um CSV inteiro de uma vez.")


if __name__ == "__main__":
    main()
