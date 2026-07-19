# Armadilhas

Os erros que custaram caro, com o que os causou e como pegá-los. Este é o
documento mais útil do conjunto — leia antes de mexer em qualquer coisa.

---

## 1. As duas metades que falavam unidades diferentes

**O sintoma:** o texto ficava encostado à esquerda dentro de uma caixa larga
demais. Parecia problema de centralização.

**A causa:** existem *duas* funções que lidam com o tamanho do texto, e só uma
tinha sido convertida.

| função | papel | estado |
|---|---|---|
| `sub_08001F14` | **desenha** o texto | convertida para pixels |
| `sub_0800B130` | **mede** o texto | ainda contava caracteres |

A segunda alimenta todo o dimensionamento de janela e toda a centralização:

```asm
bl sub_0800B130      ; n
lsls r0, r1, #1      ; 2n
adds r0, r0, r1      ; 3n
asrs r0, r0, #0xc    ; 3n/2  = n × 12px ÷ 8px por tile
adds r0, #3          ; + moldura
```

Com o VWF a letra passou a ocupar 8,34px, mas a janela continuava sendo
dimensionada a 12px por letra.

**A lição:** ao mudar a unidade de um valor, procure **todos** os produtores
dele, não só os consumidores. `grep` pelo símbolo, não pelo padrão aritmético.

---

## 2. "Exatamente 1 ocorrência" esconde a segunda

**O sintoma:** o jogo travava ao carregar o save. Só em telas com linha de texto
longa.

**A causa:** o laço que quebra a linha em pedaços de 96px tem **dois ramos** que
descontam o mesmo contador — um para o primeiro pedaço, outro para os seguintes.
O patch converteu só o primeiro. Da segunda volta em diante o laço descontava 8
(a unidade velha) de um valor em pixels, rodando ~12x mais voltas do que devia.
Cada volta aloca 768 bytes e empurra um ponteiro: corrupção de memória.

O que escondeu o bug foi a própria verificação do patch:

```python
if refs != 1 or usos != 1:
    print("ERRO")   # achou 1, passou
```

**Procurar por 1 é o que impede de achar o segundo.** O patch agora trata os dois
literais e reporta `2/2`.

**A lição:** uma checagem que exige exatamente uma ocorrência confirma a sua
suposição em vez de testá-la. Prefira listar todas as ocorrências e conferir a
contagem contra o que você espera *e por quê*.

---

## 3. O teste que validava contra o buffer errado

`comparar_blitters.py` comparava 47 glifos do desenhador novo contra o original
executado num interpretador Thumb. Dava 47/47 idênticos. E mesmo assim o
desenhador estava errado: ele combinava a cor por OR com o fundo, produzindo
índices de paleta 5 e 6 em vez de 1 e 2.

O teste usava um buffer **zerado**, onde `0 | 1 = 1` acerta por acidente. No jogo
o buffer vem pintado com a cor 4.

**A lição:** o estado inicial do teste é parte do teste. Um fixture "limpo" pode
ser justamente o caso que não acontece na prática.

---

## 4. Ordem de scripts com dependência invisível

Dois casos, no mesmo dia:

**Os acentos que sumiram.** `encoder.py` lê `_out/acentos_mapa.json` para
converter `ã` no código do jogo. Se o arquivo não existe, ele cai em
`strip_accents()` e grava `"Nao"` — **sem avisar**. E `patch_acentos.py
--reverter` apagava esse mapa. Como `migrar_para_build.py` (que injeta as
strings) tem que rodar *antes* do `patch_acentos.py` completo — exigência dos
backups de `data1.s` — a sequência revert → migrar → patch abria uma janela em
que o mapa não existia.

Corrigido de duas formas: o revert não apaga mais o mapa, e existe
`patch_acentos.py --so-mapa` que calcula a alocação sem tocar em `data1.s`.

**A tabela que sumiu.** `patch_vwf.py --reverter` apaga os arquivos gerados,
inclusive `data/ptbr_larguras.s`. Gerar a tabela *antes* do revert é perdê-la, e
o build falha no linker.

**A lição:** fallback silencioso é pior que erro. Se um dado obrigatório falta,
falhe alto. E fixe a ordem num script — `build-ptbr.sh` existe por causa
destes dois casos.

---

## 5. `adds rD, rN, #imm` só aceita 0 a 7

```
asm/code_copy.s:4764: Error: immediate value out of range
```

A forma de três registradores do `adds` em Thumb usa imediato de 3 bits. Para
valores maiores existe `adds rN, #imm8`, que exige destino igual à origem.

No caso, `adds r0, r2, #8` virou `adds r2, #8` seguido de `strb r2, [r3, #4]` —
continua em duas instruções, que é o que importa para não deslocar nada.

**A lição:** ao trocar um imediato num patch, confira a faixa da forma usada. O
montador pega, mas só depois de você já ter raciocinado errado.

---

## 6. Arredondar para cima descentraliza

O medidor devolvia `ceil(pixels / 12)`. O título "Salvar?" tem 39px reais e
virava 4 células = 48px; a centralização calculava com 48 e empurrava o texto
4,5px para a direita. "Sim" e "Não" (22px → 2 células = 24px, erro de 1px)
pareciam certos, e só o título saía torto — o que apontava para o lugar errado.

Arredondando para o mais próximo, o erro cai de 11px para no máximo 6px.

**A lição:** quando só *um* elemento parece errado, suspeite de erro proporcional
ao tamanho antes de suspeitar de lógica diferente para aquele elemento.

---

## 7. `bl` não alcança código novo

O código novo é ligado no fim da seção `rom`, a ~32 MB das funções originais. O
`bl` de Thumb alcança 4 MB. O linker resolve inserindo um *veneer* — que muda
tamanhos e desloca tudo: 19.683 faixas alteradas na primeira tentativa.

A saída é sobrescrever o início da função original com `ldr r3, =alvo+1 / bx r3`,
mantendo o tamanho. Ver [02-vwf.md](02-vwf.md).

---

## 8. Detalhes do ambiente que consumiram tempo

- **`nohup ... &` dentro de `wsl.exe` morre** quando a chamada termina — o WSL
  derruba a sessão. Use um `.sh` em arquivo, iniciado por um processo do Windows
  que fica segurando a sessão aberta.
- **Aspas se embaralham** ao passar comandos longos por `wsl.exe`. Escreva o
  script em arquivo (pelo caminho UNC), rode `sed -i 's/\r$//'`, e execute.
- **`shutil.copy2` preserva o mtime**, então o `make` não reconstrói depois de um
  revert. Os scripts chamam `.touch()` no arquivo restaurado.
- **`sed -i 's/.$//'`** apaga o último caractere de *toda* linha. Não é o mesmo
  que remover CR.

---

## O princípio geral

O padrão de falha recorrente neste projeto foi **afirmar comportamento deduzido
como se fosse medido**. Toda vez que isso aconteceu, custou uma build quebrada e
uma rodada de investigação.

O que resolveu, em ordem de utilidade:

1. Um interpretador ARM Thumb (`thumb.py`) para executar as rotinas do jogo fora
   dele, com entradas controladas.
2. Um cliente do protocolo GDB (`gdbrsp.py`) para ler registradores do jogo
   rodando no mGBA — foi assim que se descobriu que o argumento de fundo vale
   `0x44444444`.
3. O visualizador de tiles do mGBA e a análise pixel a pixel no Aseprite — dados
   que só o humano na frente da tela conseguia obter.

Quando não der para medir, **diga que não deu**. É mais barato que alterar
assembly no escuro.
