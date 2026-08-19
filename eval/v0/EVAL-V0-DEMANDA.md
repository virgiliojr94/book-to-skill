# DEMANDA — book-to-skill EVAL v0

**Objetivo único:** medir a diferença prática entre ativação autônoma e explícita, e verificar se a vantagem do pipeline full aparece onde a tese prevê — nas tarefas de aplicação, não nas factuais.

**Versão:** 1.0 — **CONGELADA**
**Convenção de evidência:** `é` (medido) · `indica` (observado, não conclusivo) · `não verificado`
**Regra transversal:** toda asserção de resultado exige o artefato que a produziu. Se o artefato não mede o que a frase afirma, o verbo muda.

> **Regra de congelamento.** Nenhuma métrica, modelo, livro, braço ou refinamento entra nesta demanda a partir daqui. Ideias surgidas durante a execução vão para um arquivo `BACKLOG-POS-V0.md` e são avaliadas depois do resultado. O modo de falha mais provável deste projeto agora não é desenhar mal o experimento — `é` continuar refinando até nunca executá-lo.

---

## 1. Contexto

Três sinais independentes apontam ativação como possível confundidor dos resultados de Skills:

| Fonte | Sinal | Verbo |
|---|---|---|
| Yi Feng (paper) | Modelos menores frequentemente não ativam Skills sozinhos; ele usa `/skill` manual | `indica` |
| Bruno Okamoto (uso) | Amora/Hermes precisa de gatilhos configurados à mão | `indica` |
| DeepSeek Harness (runtime) | Possui `whenToUse`, mas o metadado não participa plenamente do routing | `é` |

Consequência: **uma Skill boa pode parecer ruim se nunca for carregada.**

Nas evidências analisadas até aqui, não identificamos benchmark que isole essas duas variáveis. `não verificado` — a afirmação mais forte ("nenhum benchmark existente separa") exigiria revisão bibliográfica que não foi feita.

Buraco compartilhado com o paper do Yi Feng: descriptions e summaries gerados por LLM, sem avaliação de qualidade. `é`

### 1.1 As duas perguntas do v0

**Q1.** O agente deixa de usar conhecimento que já está disponível porque não ativa a Skill?

**Q2.** Quando o acesso ao conhecimento é garantido, o pipeline full ajuda mais nas tarefas que exigem *aplicar* o conhecimento — e não apenas *encontrá-lo*?

Duas perguntas são suficientes. Qualquer terceira pergunta é backlog.

---

## 2. Escopo da demanda

### 2.1 Desenho experimental

Fatorial 2×2, replicado em 2 livros.

| Eixo | Braços |
|---|---|
| **Pipeline** | Basic progressive-disclosure Skill · Full book-to-skill |
| **Ativação** | Auto (agente decide) · Explicit (`/skill` forçado) |

**Constantes obrigatórias em todas as células:** mesmo livro, mesmo modelo, mesmo host, mesmas perguntas, mesma ordem, mesma sessão limpa (`/clear` entre execuções).

**Braço "basic"** replica a pipeline do paper: chunks → resumo por chunk via LLM → `SKILL.md` com tabela/índice dos resumos. Precisa ser construído — não existe hoje no repositório. Deve ser fiel ao paper, não uma versão enfraquecida de propósito.

### 2.2 Limitações estruturais — declaradas antes de rodar

Duas limitações são inerentes ao desenho e **não** serão corrigidas no v0. Estão escritas aqui para que não sejam descobertas depois e usadas como interpretação conveniente.

**L1 — `auto` vs `explicit` não isola ativação em estado puro.**
Dependendo do host, `/skill` pode injetar conteúdo no contexto por mecanismo diferente da chamada automática da ferramenta. Se explicit > auto, parte da diferença pode vir do **mecanismo de injeção**, não apenas de ter ativado ou não.
→ Mitigação obrigatória: registrar como o host materializa cada modo. Se ambos produzirem o mesmo bloco de conteúdo antes da resposta, a limitação encolhe e isso deve ser declarado. Se não, declarar a diferença.
→ Consequência: H1 mede **a diferença prática entre ativação autônoma e explícita naquele host**, não o efeito puro de ativação.

**L2 — `full` vs `basic` compara pipelines completos, não o efeito causal isolado da estrutura semântica.**
Se o full carregar substancialmente mais conteúdo útil e vencer, isso não autoriza a conclusão "estrutura semântica venceu" — pode ser simplesmente mais informação disponível.
→ Mitigação obrigatória: registrar por braço os tokens do `SKILL.md`, tokens totais do bundle, número de arquivos e tokens efetivamente carregados por resposta.
→ Consequência: se o full vencer, o experimento seguinte controla budget e cobertura. Essa frase entra no relatório **mesmo que o resultado seja favorável**.

### 2.3 Corpus

- **Livro A** — técnico, com frameworks explícitos e decisões nomeáveis
- **Livro B** — segundo domínio, para evitar que o resultado seja artefato de um livro só

Ambos precisam ser obras que o avaliador domina o suficiente para corrigir respostas à mão.

### 2.4 Perguntas — 20 por livro

| Categoria | Qtd | Forma |
|---|---|---|
| Factual | 8 | "O que o livro diz sobre X?" |
| Aplicação | 8 | "Analise esta decisão segundo o framework do livro" |
| Crítica | 4 | "Quais trade-offs o autor apontaria neste contexto?" |

As perguntas de aplicação e crítica precisam de um **cenário concreto anexado** — decisão real, código, arquitetura. Sem cenário, a pergunta degenera em factual disfarçada.

### 2.5 Volume

2 livros × 20 perguntas × 4 células = **160 execuções**.

### 2.6 Métricas

**Primária:** taxa de ativação — proporção de execuções na condição *auto* em que o agente carregou a Skill sem ser instruído. Exige definição operacional escrita e ao menos um caso-limite classificado (mencionar o livro **não** conta como ativação).

**Secundárias:**

| Métrica | Escala | Nota |
|---|---|---|
| Aplicação do framework | 0/1/2 | Rubrica escrita antes da primeira correção |
| **Citation validity** | 0/1 | O capítulo ou referência citada existe? |
| **Source support** | 0/1/2 | A afirmação principal é de fato sustentada pela fonte? |
| Alegações não sustentadas | contagem | |
| Tokens e custo por resposta | número | |
| Tokens/arquivos por braço | número | Exigido por L2 |

Citation validity e source support são métricas **separadas** de propósito: uma resposta pode citar corretamente o Capítulo 7 e inventar por completo o que o Capítulo 7 diz. Medir só a primeira mede validade da referência, não fidelidade à fonte.

> **Impacto no orçamento:** a separação acima adiciona uma segunda passada de correção. O tripwire de 8 horas passa a disparar mais cedo. Resposta pré-definida: **cortar o Livro B, não cortar a métrica.**

### 2.7 Pré-registro de hipóteses

**Escrever em arquivo com timestamp antes de rodar qualquer célula.** Sem isso o resultado é interpretável em qualquer direção.

- **H1** — A lacuna entre auto e explicit é material naquele host, com ativação em auto < 100%. → ativação é confundidor prático real
- **H2** — Full > basic nas perguntas de aplicação e crítica
- **H3** — Full ≈ basic nas perguntas factuais

**O critério de sucesso do v0 não é um número publicável.** É preencher esta tabela:

|  | Factual | Aplicação/Crítica |
|---|---|---|
| **Basic** | ? | ? |
| **Full** | ? | ? |

- **Basic ≈ Full no factual, Full > Basic na aplicação** → primeiro sinal medido da tese que apareceu espontaneamente com o Cristian
- **Basic ≈ Full em tudo** → resultado igualmente grande: `indica` que boa parte da sofisticação do pipeline não entrega valor incremental mensurável neste workload, e a adição de complexidade por intuição deve parar

### 2.8 Artefatos colaterais obrigatórios

Registrar, verbatim:

- `name`, `description` e `whenToUse` de cada braço — texto suspeito de dominar a ativação
- Mecanismo de injeção de cada modo de ativação (exigido por L1)
- Hash do commit do book-to-skill usado na geração do braço full

---

## 3. Fora de escopo (explícito)

Nenhum destes entra no v0, independente de quão promissores pareçam durante a execução:

- Knowledge Registry / Execution Registry
- Author Mode como feature de produto
- Rights, verification, takedown, ISBN, selo oficial
- Lente `--lens dsh` no `validate_skill.py`
- Correção automatizada por LLM-as-judge
- Terceiro livro, segundo modelo, braço RAG
- Igualar artificialmente budget/cobertura entre braços (é o experimento seguinte, não este)
- Escrita de paper
- Resposta à pergunta estratégica do Wagner
- Qualquer mudança no pipeline de geração antes do resultado sair

---

## 4. Tripwires de escopo

Condições que obrigam a parar e cortar, não a expandir:

1. Correção passou de **8 horas** → cortar Livro B, rodar v0 com 1 livro e declarar a limitação
2. Construção do braço basic passou de **1 dia** → simplificar até caber; ele é baseline, não produto
3. Surgiu vontade de automatizar a correção → **não**. Em v0 ainda não se sabe o que está sendo medido
4. Surgiu vontade de consertar o pipeline no meio da execução → anotar em `BACKLOG-POS-V0.md` e continuar; corrigir invalida as células já rodadas
5. O eval começou a exigir esforço de redação acadêmica → o produto virou pesquisa; recuar
6. Surgiu um quinto ajuste de desenho depois deste congelamento → vai para o backlog, não para a demanda

---

## 5. Track B — paralelo, custo próximo de zero

Independente do eval, e com janela de tempo mais curta que ele:

| # | Ação | Informação única que produz |
|---|---|---|
| B1 | Mensagem ao Yi Feng com **uma** pergunta (auto vs explicit), não um programa de colaboração | Medição externa e independente |
| B2 | Pergunta de retenção ao Cristian: ainda usa? com que frequência? | **Único dado de retenção existente.** Hoje: `não verificado` |
| B3 | Pergunta ao Bruno: quanto trabalho manual foi necessário para a ativação funcionar? A Amora ativou errado alguma vez? | Custo humano da ativação — o laboratório não mede isso |

B2 é o item de maior razão valor/custo do documento inteiro. Post positivo ≠ retenção. "Continuo usando toda semana para decisões de modelagem" e "foi legal no dia, nunca mais usei" levam a prioridades diferentes — inclusive para o próprio eval.

B3 tem valor específico: Skill boa + duas horas configurando gatilhos `é` um problema de produto real, e nenhuma célula do eval consegue enxergá-lo.

---

## 6. CHECKLIST DE CONCLUSÃO

### Preparação

- [ ] Livro A e Livro B escolhidos e justificados por escrito
- [ ] 20 perguntas por livro redigidas, com cenário concreto anexado nas de aplicação e crítica
- [ ] Rubrica de aplicação (0/1/2) escrita **antes** da primeira correção
- [ ] Rubrica de source support (0/1/2) escrita **antes** da primeira correção
- [ ] Definição operacional de "ativou", com caso-limite classificado
- [ ] Modelo, host e versão fixados e registrados
- [ ] H1–H3 pré-registradas em arquivo, com timestamp anterior à primeira execução
- [ ] `BACKLOG-POS-V0.md` criado e vazio, pronto para receber desvios

### Construção

- [ ] Braço basic construído (chunks → resumos → SKILL.md com índice), fiel ao paper
- [ ] Braço full gerado pelo book-to-skill na versão corrente, com hash do commit registrado
- [ ] `name` / `description` / `whenToUse` de ambos os braços salvos verbatim
- [ ] Tokens do SKILL.md, tokens totais e número de arquivos registrados por braço (L2)
- [ ] Mecanismo de injeção de auto e explicit documentado (L1)

### Execução

- [ ] 160 execuções concluídas (ou 80, se o tripwire 1 tiver disparado e a limitação estiver declarada)
- [ ] `/clear` entre execuções confirmado
- [ ] Ordem das perguntas idêntica em todas as células
- [ ] Toda saída bruta arquivada, não só as notas de correção
- [ ] **Outputs anonimizados** (`run-047`, `run-122`…) com mapa condição↔ID guardado à parte

### Medição — correção cega obrigatória

- [ ] Correção feita sem acesso à condição de cada run
- [ ] Mapa de condições revelado **somente após** todas as notas fechadas
- [ ] Taxa de ativação calculada para as células auto
- [ ] Rubrica de aplicação aplicada a todas as respostas
- [ ] Citation validity aplicada
- [ ] Source support aplicado
- [ ] Alegações não sustentadas contadas
- [ ] Tokens e custo registrados por célula

### Fechamento

- [ ] H1, H2 e H3 marcadas individualmente como CONFIRMADA / REFUTADA / INCONCLUSIVA
- [ ] Tabela 2×2 (factual × aplicação, basic × full) preenchida
- [ ] L1 e L2 reproduzidas no relatório final, **mesmo que o resultado seja favorável**
- [ ] Limitações escritas: modelo único, 2 livros, avaliador único, host único
- [ ] Toda asserção do relatório carrega `é` / `indica` / `não verificado`
- [ ] Nenhum item da seção 3 foi construído durante a execução
- [ ] `BACKLOG-POS-V0.md` revisado — e só então

### Track B

- [ ] B1 enviada
- [ ] B2 enviada e respondida
- [ ] B3 enviada e respondida

---

## 7. PROTOCOLO DE REVIEW

A executar no fechamento. Cada asserção recebe um verbo e o artefato que a sustenta. Asserção sem artefato é automaticamente `não verificado`, mesmo que o avaliador esteja convencido dela.

| # | Asserção a verificar | Artefato exigido |
|---|---|---|
| R1 | As constantes experimentais foram mantidas em todas as células | Log de execução |
| R2 | As hipóteses foram registradas antes da primeira execução | Timestamp do arquivo de pré-registro |
| R3 | As rubricas não foram ajustadas depois de ver as respostas | Histórico de versão das rubricas |
| R4 | A taxa de ativação mede carregamento efetivo, não menção ao livro | Definição operacional + caso-limite classificado |
| R5 | O braço basic é fiel à pipeline do paper | `SKILL.md` do braço basic, revisável por terceiro |
| R6 | Nenhuma mudança de pipeline ocorreu durante a execução | `git log` do intervalo entre primeira e última célula |
| R7 | A correção foi cega | Mapa condição↔ID com timestamp posterior ao fechamento das notas |
| R8 | L1 e L2 constam do relatório final | Relatório |
| R9 | As conclusões não extrapolam além de 2 livros, 1 modelo, 1 host, 1 avaliador | Seção de limitações |
| R10 | Nenhum item da seção 3 entrou no escopo | Diff do repositório no período |

**Falha em R2, R3, R6 ou R7 invalida o resultado.** As quatro protegem contra a mesma coisa: decidir depois o que deveria ter sido decidido antes.

---

## 8. REVIEW DA DEMANDA (executado no congelamento)

Cobertura desta demanda contra os sinais levantados na discussão estratégica.

| Sinal / ator | Coberto? | Onde |
|---|---|---|
| Ativação como confundidor (Yi Feng, Bruno, dsh) | Sim, com L1 declarada | §2.1, §2.2, métrica primária, H1 |
| Tese "aplicado > factual" (Cristian, autor do livro de entrevistas) | Sim | §2.4, H2/H3, tabela 2×2 |
| Descriptions sem avaliação de qualidade | Parcial | §2.8 registra o artefato; o v0 **não** manipula description |
| Diferencial vs workflow manual (Bruno) | Sim, indiretamente | Full vs basic, com L2 limitando a conclusão |
| Custo humano da ativação | Sim, fora do eval | Track B3 |
| Retenção | Sim, fora do eval | Track B2 |
| Author Mode | Não, deliberado | §3 — vira testável *depois* que o eval existir |
| Conflito entre Skills (Ernesto) | Não, deliberado | Evidência hoje próxima de nula |
| Registry / rights (Gui) | Não, deliberado | §3 |
| ICP estreitado (Marcus) | Sim, implicitamente | Escolha de livros técnicos com frameworks |
| Pergunta estratégica (Wagner) | Não, com gatilho | §3 — revisitar quando v0 e resposta do Yi Feng existirem |

### 8.1 Lacunas conscientes assumidas

- **Description não é manipulada.** Se H1 se confirmar, variar description vira o experimento óbvio seguinte, e o registro da §2.8 torna esse passo barato. Ficar fora do v0 `é` decisão de escopo.
- **Efeito causal da estrutura semântica não é isolado** (L2). O experimento que controla budget e cobertura é o seguinte, não este.
- **Host único.** L1 é específica do host escolhido; generalizar exigiria repetir em um segundo runtime. Backlog.

### 8.2 Riscos residuais

- **Viés de confirmação** — mitigado por correção cega obrigatória (§6, R7). Era o maior risco não tratado da v0.9 e passou a tratado.
- **Avaliador único** — não mitigado. Mesmo cega, a correção tem um só julgamento. Declarar em limitações.
- **Corpus pequeno** — não mitigado por decisão de escopo. Declarar.

### 8.3 Correções aplicadas nesta versão

Quatro ajustes de review incorporados: reinterpretação de H1 sob L1, declaração explícita de L2 com registro de tokens/cobertura, separação de citation validity e source support, e correção cega promovida de opcional para obrigatória. Uma afirmação foi enfraquecida por não sustentar o verbo que carregava: "nenhum benchmark existente separa as duas coisas" virou uma afirmação sobre as evidências efetivamente analisadas.
