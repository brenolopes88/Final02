# Flow Directo - Oráculo Studio

Este projeto agora suporta um fluxo direto em `flow.py` para gerar conteúdo a partir de um CSV simples.

## Objetivo

Você envia um `flow.csv` com:
- `data`
- `cartas`
- `humor`

E o `flow.py` faz o resto:
1. gera roteiro via Gemini
2. gera voz com o preset de humor escolhido
3. monta vídeo final com BG e música aleatória
4. salva roteiro, voz e vídeo juntos em `projects/<nome_do_projeto>/`

## Arquivos criados
- `flow.py` – orquestrador principal
- `flow_sample.csv` – exemplo de entrada

## Formato do CSV
Use o arquivo `flow_sample.csv` como referência.

Colunas obrigatórias:
- `data` — formato `DD/MM`, `DD-MM`, ou `DDMM`
- `cartas` — uma ou duas cartas (separadas por `,`, `;` ou `|`)
- `humor` — um dos presets:
  - `Padrão`
  - `Solene`
  - `Intenso`
  - `Meditativo`

### Exemplo
```
data,cartas,humor
28/07,Imperatriz,Padrão
29/07,Dois de Copas;A Estrela,Intenso
30/07,O Eremita,Meditativo
```

## Regras de normalização
- `humor` aceita variações como `padrao`, `padrão`, `solene`, `intenso`, `meditativo`
- `cartas` aceita separadores `,`, `;` e `|`
- `data` é validada e formatada internamente como `DD-MM`
- `periodo` é inferido: 1 carta = `MANHÃ`, 2 cartas = `NOITE`

## Saída
Para cada linha válida, o `flow.py` salva em uma pasta única:
- `projects/<DD-MM>_<período>_<cartas>/roteiro.json`
- `projects/<...>/voz.wav`
- `projects/<...>/<nome_do_projeto>.mp4`
- `projects/<...>/legenda.txt`

## Executar
Ative o ambiente virtual e rode:

```powershell
.\.venv\Scripts\python.exe flow.py
```

### Opcional
- `--csv <arquivo>` — usa outro CSV
- `--dry-run` — valida o CSV sem gerar artefatos
- `--sample` — cria `flow_sample.csv`

## Observações
- O restante do projeto não foi alterado.
- O vídeo usa backgrounds e música aleatória dos diretórios `inputs/videos_fundo/` e `inputs/audio_assets/`.
- A voz é gerada com um preset diretamente alinhado ao `humor`.
