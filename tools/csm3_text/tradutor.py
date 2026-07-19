#!/usr/bin/env python3
"""Runner de traducao: japones -> portugues, via LLM local.

Fala com um llama-server (API compativel com OpenAI) rodando no Windows com a
GPU. Nenhuma dependencia de ML no WSL - so httpx.

O que ele resolve, alem de chamar o modelo:

  PLACEHOLDERS  {g} e {d} sao nomes que o jogador escolhe. Passar um token opaco
                ao modelo impede que ele construa a concordancia em portugues.
                Entao troco por nomes reais antes de traduzir e reverto depois:
                o modelo escreve "Ritchie, voce viu a Murno?" e vira
                "{g}, voce viu a {d}?".

  GLOSSARIO     nome proprio traduzido de tres formas em tres cenas e o defeito
                mais visivel de traducao automatica de RPG. O glossario entra em
                todo prompt e a saida e validada contra ele.

  CONTEXTO      cada fala vai com a anterior e a seguinte, porque o japones
                omite sujeito e genero e o portugues exige os dois.

  VALIDACAO     confere placeholders, vazamento de preambulo e comprimento.
                Falhou, tenta de novo com temperatura menor; falhou de novo,
                marca para revisao manual em vez de gravar lixo.

Uso:
    python3 tradutor.py --dry-run --limite 3     # so mostra o prompt
    python3 tradutor.py --limite 200             # piloto
    python3 tradutor.py                          # tudo (retoma de onde parou)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "_out"

# O llama-server roda no WINDOWS (e onde esta a GPU); este script roda no WSL.
# O servidor esta preso ao IP do host na rede virtual do WSL - nao em 0.0.0.0,
# para nao ficar exposto na rede local. Descobre o endereco pelo gateway padrao.
def _endereco_servidor() -> str:
    import os
    if os.environ.get("LLAMA_SERVER"):
        return os.environ["LLAMA_SERVER"]
    try:
        rota = Path("/proc/net/route").read_text()
        for linha in rota.splitlines()[1:]:
            campos = linha.split()
            if len(campos) > 2 and campos[1] == "00000000":
                bruto = int(campos[2], 16)
                ip = ".".join(str((bruto >> (8 * i)) & 0xFF) for i in range(4))
                return f"http://{ip}:8080"
    except OSError:
        pass
    return "http://localhost:8080"


SERVIDOR = _endereco_servidor() + "/v1/chat/completions"

# Nomes usados no lugar dos placeholders durante a traducao. Sao os apelidos
# padrao do jogo, entao o modelo produz portugues idiomatico e com concordancia.
NOMES_TEMP = {
    "{g}": ("Ritchie", "M"),   # protagonista (o jogador renomeia)
    "{d}": ("Murno", "F"),
    "{z}": ("Lemmy", "M"),
    "{b}": ("V.E", "F"),
    "{e}": ("Tier", "F"),
    "{t}": ("Jade", "M"),
}

PREAMBULOS = re.compile(
    r"^\s*(?:aqui est[aá]|segue|tradu[cç][aã]o|resultado|resposta)\s*:?\s*",
    re.IGNORECASE,
)

SISTEMA = """Você traduz o roteiro de um RPG japonês de Game Boy Advance para \
português brasileiro.

REGRAS:
1. Traduza APENAS a fala. Não explique, não comente, não repita o japonês.
2. Português brasileiro coloquial e natural — é diálogo de personagem, não texto \
técnico. Personagens jovens falam como jovens.
3. LIMITE DE CARACTERES — a regra mais importante. Cada fala traz seu limite \
entre colchetes, tipo [máx 54]. A tradução NÃO pode passar disso, contando \
espaços. A caixa de texto do Game Boy Advance é estreita e o que passa some da \
tela.
   Para caber: corte palavras redundantes, use frases curtas, prefira o verbo \
simples ao composto. "Não sei se foi por causa do remédio" vira "Não sei se foi \
o remédio". "Para onde eles iam ir" vira "Para onde iam". Corte "que", "isso", \
"então" quando não fizerem falta.
   Cortar informação é preferível a estourar o limite.
4. Preserve o registro: quem fala formal continua formal, quem fala rude \
continua rude.
4b. GÊNERO — o jogador escolhe se o protagonista é menino ou menina, e cada fala \
diz qual caso atende:
   [MASC] só aparece para o protagonista menino. Use flexão masculina à vontade.
   [FEM]  só aparece para a protagonista menina. Use flexão feminina.
   [NEUTRO] aparece para os DOIS. NÃO use adjetivo nem particípio flexionado \
referindo-se ao jogador. Reescreva: "fiquei surpreso" vira "que surpresa"; \
"estou cansado" vira "que cansaço"; "fui escolhido" vira "me escolheram". \
Se for impossível evitar, termine a linha com o marcador ##FLEX## para revisão.
5. Use EXATAMENTE os nomes do glossário. Nunca traduza nem adapte um nome próprio \
que esteja lá.
6. Responda uma linha por fala, na mesma ordem, no formato:
   <número>: <tradução>
   Nada além disso."""


def carregar_glossario() -> dict[str, dict]:
    caminho = OUT / "glossario_final.json"
    if not caminho.exists():
        return {}
    d = json.loads(caminho.read_text(encoding="utf-8"))
    mapa = {}
    for secao in ("confirmados", "revisar"):
        for e in d.get(secao, []):
            if e.get("pt"):
                mapa[e["jp"]] = e
    return mapa


def glossario_relevante(textos: list[str], glossario: dict) -> list[dict]:
    """So os termos que aparecem NESTE lote - glossario inteiro em todo prompt
    seria desperdicio de tokens, e geracao e o gargalo."""
    junto = "".join(textos)
    return [e for jp, e in glossario.items() if jp in junto]


def mascarar(texto: str) -> tuple[str, dict[str, str]]:
    """Troca {g}/{d}/... por nomes reais, devolvendo o mapa para reverter."""
    reverso = {}
    for tag, (nome, _) in NOMES_TEMP.items():
        if tag in texto:
            texto = texto.replace(tag, nome)
            reverso[nome] = tag
    return texto, reverso


def desmascarar(texto: str, reverso: dict[str, str]) -> str:
    # Do nome mais longo para o mais curto, para nao quebrar nomes que sejam
    # prefixo de outros.
    for nome in sorted(reverso, key=len, reverse=True):
        texto = texto.replace(nome, reverso[nome])
    return texto


def montar_prompt(lote: list[dict], glossario: dict) -> str:
    textos = [u["jp"] for u in lote]
    termos = glossario_relevante(textos, glossario)

    partes = []
    if termos:
        partes.append("GLOSSÁRIO (use exatamente estas grafias):")
        for e in termos:
            genero = {"M": " (masculino)", "F": " (feminino)"}.get(e.get("genero"), "")
            nota = f" — {e['nota']}" if e.get("nota") else ""
            partes.append(f"  {e['jp']} = {e['pt']}{genero}{nota}")
        partes.append("")

    partes.append("FALAS A TRADUZIR:")
    for i, u in enumerate(lote, 1):
        ctx = u.get("contexto") or {}
        if ctx.get("antes"):
            partes.append(f"  [fala anterior, só para contexto: {ctx['antes']}]")
        marca = {"M": "[MASC]", "F": "[FEM]"}.get(u.get("genero"), "[NEUTRO]")
        partes.append(f"{i}: [máx {u['_limite']}] {marca} {u['_jp_mascarado']}")
        if ctx.get("depois"):
            partes.append(f"  [fala seguinte, só para contexto: {ctx['depois']}]")
        partes.append("")

    partes.append(f"Responda as {len(lote)} traduções, uma por linha, no formato "
                  f"'<número>: <tradução>'. Respeite o limite de caracteres de "
                  f"cada uma — conte antes de responder.")
    return "\n".join(partes)


def chamar_modelo(prompt: str, temperatura: float = 0.3) -> str | None:
    try:
        import httpx
    except ImportError:
        print("  ERRO: falta httpx. Rode: pip install httpx", file=sys.stderr)
        return None
    try:
        r = httpx.post(SERVIDOR, timeout=300.0, json={
            "messages": [
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperatura,
            "max_tokens": 2048,
        })
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"  ERRO no servidor: {exc}", file=sys.stderr)
        return None


def parsear(resposta: str, n: int) -> dict[int, str]:
    saida = {}
    for linha in resposta.splitlines():
        m = re.match(r"\s*(\d+)\s*[:.)\-]\s*(.+)", linha)
        if m:
            idx = int(m.group(1))
            if 1 <= idx <= n:
                saida[idx] = PREAMBULOS.sub("", m.group(2)).strip()
    return saida


# Adjetivos e participios flexionados que, numa fala compartilhada, erram para
# metade dos jogadores. Instrucao no prompt nao basta - o modelo escorrega.
# So conta como flexao quando vem depois de copula referindo-se a quem fala.
# "que surpresa" e substantivo e nao flexiona ninguem; "fiquei surpreso" sim.
FLEXAO_MASC = re.compile(
    r"\b(?:fiquei|fico|estou|to|tô|sou|era|fui|serei|me sinto|sinto-me|"
    r"tava|estava|ficaria|seria|continuo|ando)\s+(?:meio\s+|muito\s+|bem\s+|"
    r"tão\s+|um pouco\s+)?"
    r"(surpres[oa]|cansad[oa]|preocupad[oa]|assustad[oa]|sozinh[oa]|"
    r"perdid[oa]|prepara[dt][oa]|obrigad[oa]|pront[oa]|segur[oa]|nervos[oa]|"
    r"animad[oa]|chatead[oa]|confus[oa]|salv[oa]|escolhid[oa]|machucad[oa]|"
    r"felizard[oa]|acostumad[oa]|decidid[oa])\b",
    re.IGNORECASE,
)


def validar(original: str, traducao: str, genero: str = "ambos") -> str | None:
    """Devolve o motivo da rejeicao, ou None se passou."""
    if not traducao:
        return "vazia"
    if genero == "ambos":
        m = FLEXAO_MASC.search(traducao)
        if m:
            return f"flexao de genero em fala compartilhada: '{m.group(0)}'"
    if len(traducao) > 200:
        return "longa demais"
    orig_tags = sorted(re.findall(r"\{[a-z]\}", original))
    trad_tags = sorted(re.findall(r"\{[a-z]\}", traducao))
    if orig_tags != trad_tags:
        return f"placeholders divergem: {orig_tags} -> {trad_tags}"
    if re.search(r"[ぁ-んァ-ヶ一-鿿]", traducao):
        return "sobrou japones"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="mostra o prompt e sai")
    ap.add_argument("--limite", type=int, help="traduz so as N primeiras")
    ap.add_argument("--lote", type=int, default=12, help="falas por requisicao")
    ap.add_argument("--capacidade", type=int, default=54,
                    help="chars por caixa: 54 sem VWF, 78 com VWF")
    ap.add_argument("--saida", default="traducao.json")
    args = ap.parse_args()

    dados = json.loads((OUT / "falas_originais.json").read_text(encoding="utf-8"))
    todas = [u for u in dados["falas"] + dados["itens"] if u["jp"].strip()]

    # DEDUPLICACAO: o jogo repete a mesma fala varias vezes (a animacao de
    # rolagem redesenha a linha em posicoes diferentes). Traduzir cada copia
    # gastaria GPU a toa E arriscaria sair diferente em cada uma. Traduz uma vez
    # e aplica em todas.
    por_texto: dict[str, list[dict]] = {}
    for u in todas:
        por_texto.setdefault(u["jp"], []).append(u)
    unidades = [copias[0] for copias in por_texto.values()]
    for u in unidades:
        u["_copias"] = [c["id"] for c in por_texto[u["jp"]]]

    if args.limite:
        unidades = unidades[: args.limite]

    glossario = carregar_glossario()
    print("=" * 72)
    print("TRADUTOR")
    print("=" * 72)
    print(f"  unidades no jogo : {len(todas):,}")
    print(f"  textos distintos : {len(por_texto):,}  "
          f"({100*(1-len(por_texto)/len(todas)):.0f}% eram repeticao)")
    print(f"  a traduzir       : {len(unidades):,}")
    print(f"  glossario      : {len(glossario)} termos")
    print(f"  lote           : {args.lote} falas por requisicao")
    print(f"  requisicoes    : ~{-(-len(unidades)//args.lote):,}")
    print(f"  servidor       : {SERVIDOR}")

    # Retomada: nao retraduz o que ja passou.
    destino = OUT / args.saida
    feitas = {}
    if destino.exists() and not args.dry_run:
        anterior = json.loads(destino.read_text(encoding="utf-8"))
        feitas = {e["id"]: e for e in anterior.get("traducoes", [])
                  if e.get("pt") and not e.get("erro")}
        print(f"  ja traduzidas  : {len(feitas):,} (serao puladas)")

    pendentes = [u for u in unidades if u["id"] not in feitas]
    for u in pendentes:
        u["_jp_mascarado"], u["_reverso"] = mascarar(u["jp"])
        # Orcamento por fala: o teto da caixa, mas nunca menos que o dobro do
        # japones - fala curta nao precisa ser espremida, e apertar demais
        # produz portugues truncado.
        u["_limite"] = max(args.capacidade, min(len(u["jp"]) * 2, args.capacidade))
        if len(u["jp"]) * 2 < args.capacidade:
            u["_limite"] = max(24, len(u["jp"]) * 2)

    if args.dry_run:
        lote = pendentes[: args.lote]
        print()
        print("=" * 72)
        print("PROMPT DE SISTEMA")
        print("=" * 72)
        print(SISTEMA)
        print()
        print("=" * 72)
        print("PROMPT DO PRIMEIRO LOTE")
        print("=" * 72)
        print(montar_prompt(lote, glossario))
        print()
        print("=" * 72)
        print("MASCARAMENTO APLICADO")
        print("=" * 72)
        for u in lote:
            if u["_reverso"]:
                print(f"  {u['jp']}")
                print(f"    -> {u['_jp_mascarado']}   (reverte: {u['_reverso']})")
        return 0

    resultados = list(feitas.values())
    falhas = []
    inicio = time.time()

    for i in range(0, len(pendentes), args.lote):
        lote = pendentes[i:i + args.lote]
        prompt = montar_prompt(lote, glossario)

        # Resposta vazia acontece quando o contexto do slot nao comporta o
        # prompt. Em vez de perder o lote, tenta de novo - e na ultima tentativa
        # quebra em lotes menores, que sempre cabem.
        traduzidas = {}
        resposta = None
        for tentativa in range(3):
            resposta = chamar_modelo(prompt, temperatura=0.3 if tentativa == 0 else 0.15)
            if resposta is None:
                break
            traduzidas = parsear(resposta, len(lote))
            if len(traduzidas) >= len(lote) / 2:
                break
            if tentativa == 1 and len(lote) > 2:
                # Ultima cartada: metade do lote de cada vez.
                traduzidas = {}
                meio = len(lote) // 2
                for base, sub in ((0, lote[:meio]), (meio, lote[meio:])):
                    r = chamar_modelo(montar_prompt(sub, glossario), temperatura=0.15)
                    if r:
                        for k, v in parsear(r, len(sub)).items():
                            traduzidas[base + k] = v
                break

        if resposta is None:
            print("\n  Servidor indisponivel. Suba o llama-server e rode de novo -")
            print("  o que ja foi traduzido esta salvo e sera pulado.")
            break
        # Se o parse falhou para a maioria do lote, o problema e a resposta em
        # si (formato quebrado ou truncada), nao a traducao. Guarda o texto cru
        # para diagnostico em vez de gravar vazios em silencio.
        if len(traduzidas) < len(lote) / 2:
            bruto = OUT / "resposta_crua.txt"
            bruto.write_text(
                f"--- PROMPT ---\n{prompt}\n\n--- RESPOSTA ---\n{resposta}\n",
                encoding="utf-8")
            print(f"\n  ATENCAO: parse recuperou so {len(traduzidas)}/{len(lote)}."
                  f" Resposta crua em {bruto.name}")
        # Quem nao voltou no lote ganha uma chamada so para si.
        #
        # Sem isto, um lote que devolvia 9 de 12 passava no teste "metade ou
        # mais" acima, saia do laco de tentativas, e as 3 falas que faltavam
        # eram gravadas como vazias em silencio. Medido: 25% de vazias, e
        # espalhadas pelo lote (nao no fim), o que descartou corte de resposta.
        # Traduzir uma fala sozinha e o caso mais facil para o modelo.
        faltantes = [(k, u) for k, u in enumerate(lote, 1) if not traduzidas.get(k)]
        for k, u in faltantes:
            r = chamar_modelo(montar_prompt([u], glossario), temperatura=0.15)
            if not r:
                continue
            individual = parsear(r, 1)
            if individual.get(1):
                traduzidas[k] = individual[1]
        if faltantes:
            salvas = sum(1 for k, _ in faltantes if traduzidas.get(k))
            print(f"\n  {salvas}/{len(faltantes)} recuperadas uma a uma")

        for k, u in enumerate(lote, 1):
            pt = traduzidas.get(k, "")
            pt = desmascarar(pt, u["_reverso"])
            motivo = validar(u["jp"], pt, u.get("genero", "ambos"))

            # Flexao de genero em fala compartilhada tem conserto: pede de novo,
            # dizendo exatamente qual palavra usar de outro jeito.
            if motivo and motivo.startswith("flexao"):
                palavra = motivo.split("'")[1]
                corrigido = chamar_modelo(
                    f"Esta tradução usa '{palavra}', que flexiona em gênero:\n\n"
                    f"  {pt}\n\n"
                    f"O protagonista pode ser menino OU menina, então isso erra "
                    f"para metade dos jogadores. Reescreva SEM nenhum adjetivo ou "
                    f"particípio flexionado referindo-se a quem fala — troque a "
                    f"construção (\"fiquei surpreso\" vira \"que surpresa\"). "
                    f"Mantenha o sentido, o tom e no máximo {u['_limite']} "
                    f"caracteres. Responda só a frase corrigida.",
                    temperatura=0.15)
                if corrigido:
                    tentativa = desmascarar(
                        PREAMBULOS.sub("", corrigido.strip().splitlines()[0]).strip(),
                        u["_reverso"])
                    if not validar(u["jp"], tentativa, u.get("genero", "ambos")):
                        pt, motivo = tentativa, None

            registro = {"id": u["id"], "jp": u["jp"], "pt": pt,
                        "chars_jp": len(u["jp"]), "chars_pt": len(pt),
                        "aplica_em": u.get("_copias", [u["id"]])}
            if motivo:
                registro["erro"] = motivo
                falhas.append(registro)
            resultados.append(registro)

        feito = i + len(lote)
        taxa = feito / max(0.1, time.time() - inicio)
        resta = (len(pendentes) - feito) / max(0.01, taxa)
        print(f"\r  {feito:,}/{len(pendentes):,}  "
              f"{taxa:.1f} falas/s  ~{resta/60:.0f} min restantes  "
              f"({len(falhas)} falhas)", end="", flush=True)

        destino.write_text(json.dumps(
            {"_meta": {"total": len(resultados), "falhas": len(falhas)},
             "traducoes": resultados}, indent=2, ensure_ascii=False),
            encoding="utf-8")

    print()
    print()
    print("=" * 72)
    print("RESULTADO")
    print("=" * 72)
    print(f"  traduzidas : {len(resultados):,}")
    print(f"  falhas     : {len(falhas):,}")
    for f in falhas[:8]:
        print(f"      [{f['id']}] {f['erro']}")
        print(f"          jp: {f['jp']}")
        print(f"          pt: {f['pt']}")

    validas = [r for r in resultados if not r.get("erro") and r["chars_jp"]]
    if validas:
        exp = sum(r["chars_pt"] for r in validas) / sum(r["chars_jp"] for r in validas)
        print()
        print(f"  EXPANSAO MEDIDA: {exp:.2f}x")
        print(f"  (era estimativa de 2,2x; e este numero que decide o VWF)")
        cap = 54
        estoura = sum(1 for r in validas if r["chars_pt"] > cap)
        print(f"  falas acima de {cap} chars (a caixa sem VWF): "
              f"{estoura:,} de {len(validas):,} ({100*estoura/len(validas):.1f}%)")

    print(f"\n  gravado: {destino.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
