# tools/csm3_text

O pipeline da tradução, e as ferramentas de medição que sustentam o que está
documentado em [`../../docs/`](../../docs/).

São muitos scripts porque **quase toda afirmação sobre o comportamento do jogo
aqui foi medida, não deduzida** — e cada medição virou um arquivo que pode ser
rodado de novo. Isso é proposital: ver [06-armadilhas.md](../../docs/06-armadilhas.md).

Nada aqui deve ser executado solto para construir a ROM. Use
[`../../build-ptbr.sh`](../../build-ptbr.sh), que fixa a ordem.

---

## O caminho principal

Na ordem em que o `build-ptbr.sh` chama:

| script | o que faz |
|---|---|
| `patch_acentos.py --so-mapa` | aloca os 25 glifos acentuados e grava o mapa, sem tocar em `data1.s` |
| `migrar_para_build.py` | injeta as strings de sistema traduzidas e reaponta os ponteiros |
| `patch_acentos.py` | compõe e grava os bitmaps das acentuadas na fonte |
| `gerar_larguras.py` | mede cada glifo e gera `data/ptbr_larguras.s` |
| `gerar_renderer_vwf.py` | gera o renderizador VWF a partir do original |
| `patch_vwf.py` | aplica os desvios e as conversões de unidade no assembly |
| `verificar_vwf.py` | confere que nada deslocou na ROM |

## Extração e tradução

| script | o que faz |
|---|---|
| `export_falas.py` | extrai as 21.059 falas com contexto |
| `marcar_genero.py` / `mapear_genero.py` | marca cada fala como M, F ou compartilhada |
| `extrair_glossario.py` / `montar_glossario.py` / `glossario_limpo.py` | glossário a partir do patch v1.0 |
| `tradutor.py` | roda o modelo, valida, retenta individualmente o que falhar |
| `auditar_traducao.py` | procura os defeitos que importam num RPG |
| `sysstrings.py` / `traduzir_sistema.py` | as strings de menu de sistema |
| `inject.py` / `inject_sys.py` | injeção com reflow e realocação de blobs |

## O formato do jogo

| script | o que faz |
|---|---|
| `csm3rom.py` | acesso aos arquivos empacotados |
| `lz77.py` | compressão BIOS tipo 0x10 (o compressor sai 0,5% menor que o original) |
| `walker.py` | caminha pelo bytecode, incluindo expressões RPN |
| `opcode_spec.py` | tamanhos dos opcodes, carregados de `_out/sequences.json` |
| `verify_roundtrip.py` | **critério de aceitação**: 0 opcodes desconhecidos, 0 saltos inválidos |
| `font.py` / `encoder.py` | fonte e codificação Shift-JIS |
| `acentos.py` | composição dos glifos acentuados |

## Medição — a origem do que está em `docs/`

Estes não fazem parte do build. Existem porque cada um respondeu uma pergunta
que eu tinha errado antes de medir.

| script | o que mediu |
|---|---|
| `thumb.py` | **interpretador ARM Thumb** — executa rotinas do jogo fora dele |
| `mapear_destino.py` | o layout do buffer de destino do desenhador |
| `medir_sombra.py` | o deslocamento das sombras |
| `mapear_nibbles.py` | a ordem das metades de byte por coluna |
| `comparar_blitters.py` | o desenhador novo contra o original, glifo a glifo |
| `comparar_render.py` | quanto de tinta e de sombra se perde com cada avanço |
| `medir_bearing.py` | por que o espaçamento era irregular (3px a 8px) |
| `gerar_previa.py` | PNG comparando folgas de 0 a 3px, para escolher olhando |
| `ver_acentos.py` / `ver_render_acento.py` | as acentuadas na ROM construída |
| `medir_expansao.py` / `custo_sem_vwf.py` | quanto o português cresce, e o que o VWF salva |
| `verificar_build.py` / `risco_shift.py` / `drift.py` | conferem que nada deslocou |

## Diagnóstico

Escritos para responder a uma falha específica; ficam como registro.

`diagnosticar_vazias.py` (por que 25% das falas voltavam vazias),
`ver_falhas.py`, `ver_slot_acento.py`, `ver_largura_acento.py`, `ver_menu.py`,
`ver_bytes_menu.py`, `caçar_nao.py`, `checar_buracos.py`,
`checar_sobreposicao.py`, `checar_desvio.py`, `colher_workflow.py`.

## Exploratórios

Os prefixados com `_` (`_verify_*`, `_indep_*`) e vários `find_*` / `dump_*` /
`survey.py` são da fase de mapeamento inicial do formato do script. Estão aqui
por completude; o resultado deles está consolidado em `_out/sequences.json` e em
[04-formato-do-texto.md](../../docs/04-formato-do-texto.md).

---

## `_out/`

O que está versionado:

| arquivo | conteúdo |
|---|---|
| `traducao.json` | as traduções PT-BR |
| `sysstrings.json` | strings de menu de sistema |
| `ui_originais.json` | as 525 strings de interface, ainda em japonês |
| `glossario*.json` | grafias fixadas |
| `sequences.json` / `opcodes.json` / `handlers.json` | o formato do bytecode |
| `acentos_mapa.json` / `acentos_slots.json` | onde as acentuadas foram parar |
| `manifest.json` | inventário dos blobs |

`textos_originais.json` e `falas_originais.json` (15 MB cada) ficam de fora: são
extraídos da ROM em segundos por `export_falas.py`.

---

## Ambiente

`preparar_ambiente.sh` instala as dependências Python. `rodar_tradutor.sh` sobe o
tradutor de forma que sobreviva ao encerramento da chamada do WSL — ver a seção
de ambiente em [06-armadilhas.md](../../docs/06-armadilhas.md).
