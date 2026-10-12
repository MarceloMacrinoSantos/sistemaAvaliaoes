<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, fmtData } from '../../api'
import Grafico from '../../components/Grafico.vue'

// Paleta categórica validada (ordem fixa: a cor segue a turma, não a posição)
const CORES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']
const AZUL = '#2a78d6'
const RAMPA = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95']

const escolas = ref([])
const turmas = ref([])
const disciplinas = ref([])
const filtro = ref({ escola_id: '', turma_id: '', disciplina_id: '', inicio: '', fim: '', corte: 60 })
const dados = ref(null)
const erro = ref('')
const carregando = ref(false)

const turmasFiltradas = computed(() => turmas.value.filter((t) => !filtro.value.escola_id || t.escola_id === +filtro.value.escola_id))
const disciplinasFiltradas = computed(() => {
  const vistos = new Set()
  return disciplinas.value.filter((d) => (!filtro.value.escola_id || !d.escola_id || d.escola_id === +filtro.value.escola_id)
    && !vistos.has(d.id) && vistos.add(d.id))
})
const fmt = (n, suf = '%') => (n == null ? '—' : `${n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}${suf}`)

async function carregar() {
  erro.value = ''
  carregando.value = true
  const f = filtro.value
  const qs = new URLSearchParams()
  for (const k of ['escola_id', 'turma_id', 'disciplina_id']) if (f[k]) qs.set(k, f[k])
  if (f.inicio) qs.set('inicio', new Date(f.inicio + 'T00:00').toISOString())
  if (f.fim) qs.set('fim', new Date(f.fim + 'T23:59').toISOString())
  qs.set('corte', f.corte || 60)
  try { dados.value = await api('/api/analises?' + qs) } catch (e) { erro.value = e.message } finally { carregando.value = false }
}
onMounted(async () => {
  ;[escolas.value, turmas.value, disciplinas.value] = await Promise.all([api('/api/escolas'), api('/api/turmas'), api('/api/disciplinas')])
  carregar()
})
watch(filtro, carregar, { deep: true })

// A mesma prova aplicada em várias turmas vira uma coluna/ponto só (agrupada pelo título, em ordem de aplicação)
const grupos = computed(() => {
  const g = []
  for (const a of dados.value?.avaliacoes || []) {
    let item = g.find((x) => x.titulo === a.titulo)
    if (!item) g.push((item = { titulo: a.titulo, data: a.data, avs: [] }))
    item.avs.push(a)
  }
  return g
})

// ---------- evolução por avaliação (uma linha por turma, máx. 4) ----------
const corDaTurma = computed(() => {
  const ids = [...new Set((dados.value?.turmas || []).map((t) => t.id))].sort((a, b) => a - b)
  return Object.fromEntries(ids.map((id, i) => [id, CORES[i] || null]))
})
const muitasTurmas = computed(() => (dados.value?.turmas.length || 0) > 4)
const evolucao = computed(() => {
  if (!dados.value?.avaliacoes.length || muitasTurmas.value) return null
  const gs = grupos.value
  const labels = gs.map((g) => `${g.titulo} (${new Date(g.data).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })})`)
  const series = dados.value.turmas.map((t) => ({
    label: t.nome, data: gs.map((g) => g.avs.find((a) => a.turma_id === t.id)?.media ?? null), spanGaps: true,
    borderColor: corDaTurma.value[t.id], backgroundColor: corDaTurma.value[t.id], borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0.2
  }))
  series.push({ label: `Corte (${dados.value.corte}%)`, data: gs.map(() => dados.value.corte), borderColor: '#9a9893',
    borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 0, fill: false })
  return { labels, datasets: series }
})
const opcoesPct = { scales: { y: { min: 0, max: 100, ticks: { callback: (v) => v + '%' } } } }

// ---------- comparativo por turma ----------
const comparativo = computed(() => {
  const ts = dados.value?.turmas.filter((t) => t.media != null) || []
  if (ts.length < 2) return null
  return { labels: ts.map((t) => t.nome), datasets: [{ label: 'Média da turma', data: ts.map((t) => t.media),
    backgroundColor: ts.map((t) => corDaTurma.value[t.id] || AZUL), borderRadius: 4, borderSkipped: 'start', maxBarThickness: 28 }] }
})
const opcoesComparativo = computed(() => ({
  indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: (ctx) => {
    const t = dados.value.turmas.filter((x) => x.media != null)[ctx.dataIndex]
    return [`Aprovação: ${fmt(t.aprovacao)}`, `Participação: ${fmt(t.participacao)}`]
  } } } },
  scales: { x: { min: 0, max: 100, grid: { color: '#ebeae6' }, ticks: { callback: (v) => v + '%' } }, y: { grid: { display: false } } }
}))

// ---------- distribuição ----------
const distribuicao = computed(() => dados.value?.resumo.provas_corrigidas ? {
  labels: dados.value.distribuicao.map((f) => f.faixa),
  datasets: [{ label: 'Provas', data: dados.value.distribuicao.map((f) => f.qtd), backgroundColor: AZUL, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 40 }]
} : null)
const opcoesDistribuicao = { plugins: { legend: { display: false } }, scales: { y: { ticks: { precision: 0 } } } }

// ---------- questões difíceis ----------
const dificeis = computed(() => {
  const qs = dados.value?.questoes_dificeis || []
  if (!qs.length) return null
  const variasTurmas = new Set(qs.map((q) => q.turma)).size > 1
  return { labels: qs.map((q) => `${q.avaliacao} · Q${q.numero}` + (variasTurmas ? ` · ${q.turma}` : "")), datasets: [{ label: 'Aproveitamento', data: qs.map((q) => q.aproveitamento),
    backgroundColor: AZUL, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 22 }] }
})
const opcoesDificeis = computed(() => ({
  indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: {
    title: (it) => { const q = dados.value.questoes_dificeis[it[0].dataIndex]; return `${q.avaliacao} · Questão ${q.numero} (${q.tipo})` },
    afterLabel: (ctx) => { const q = dados.value.questoes_dificeis[ctx.dataIndex]
      const l = [q.enunciado.slice(0, 80) + (q.enunciado.length > 80 ? '…' : '')]
      if (q.distrator) l.push(`Erro mais comum: "${q.distrator.texto}" (${q.distrator.percentual}%)`)
      return l } } } },
  scales: { x: { min: 0, max: 100, grid: { color: '#ebeae6' }, ticks: { callback: (v) => v + '%' } }, y: { grid: { display: false } } }
}))

// ---------- mapa de notas (aluno × avaliação) ----------
const mapaAvs = computed(() => grupos.value.filter((g) => g.avs.some((a) => a.encerrada || a.enviadas)).slice(-12))
// nota do aluno numa coluna (a avaliação daquela prova na turma dele); undefined = não se aplica
function notaEm(al, g) {
  const av = g.avs.find((a) => a.id in al.notas)
  return av ? { tem: true, v: al.notas[av.id] } : { tem: false }
}
function corCelula(v) {
  if (v == null) return { background: '#f0efec', color: '#6b6a66' }
  const i = Math.min(RAMPA.length - 1, Math.round((v / 100) * (RAMPA.length - 1)))
  return { background: RAMPA[i], color: i >= 7 ? '#fff' : '#0b0b0b' }
}
const ordemAlunos = ref('media')
const alunosOrdenados = computed(() => {
  const l = [...(dados.value?.alunos || [])]
  if (ordemAlunos.value === 'nome') l.sort((a, b) => a.nome.localeCompare(b.nome))
  return l
})
const somenteAtencao = ref(true)
const alunosAtencao = computed(() => (dados.value?.alunos || []).filter((a) => !somenteAtencao.value || a.atencao.length))

const imprimir = () => window.print()

function baixarCsv() {
  const avs = mapaAvs.value
  const linhas = [['Aluno', 'RM', 'Média (%)', 'Tendência (p.p.)', 'Não feitas', 'Saídas da prova', ...avs.map((g) => `${g.titulo} (%)`), 'Atenção']]
  for (const a of alunosOrdenados.value) {
    linhas.push([a.nome, a.login, a.media ?? '', a.tendencia ?? '', a.faltas, a.saidas,
      ...avs.map((g) => { const n = notaEm(a, g); return n.tem ? (n.v ?? 'não fez') : '' }), a.atencao.join(' | ')])
  }
  const csv = '﻿' + linhas.map((l) => l.map((v) => `"${String(v).replace('.', ',').replace(/"/g, '""')}"`).join(';')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  Object.assign(document.createElement('a'), { href: url, download: 'analise_alunos.csv' }).click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="cabecalho">
    <div>
      <h1>Análises</h1>
      <p class="sub">Como suas turmas estão indo: evolução, pontos fracos do conteúdo e alunos que precisam de atenção.</p>
    </div>
    <div class="acoes nao-imprimir">
      <button class="sec" @click="baixarCsv" :disabled="!dados?.alunos.length">Baixar planilha</button>
      <button class="sec" @click="imprimir">Imprimir</button>
    </div>
  </div>

  <div class="card filtros nao-imprimir">
    <div><label>Escola</label>
      <select v-model="filtro.escola_id" @change="filtro.turma_id = ''; filtro.disciplina_id = ''">
        <option value="">Todas</option><option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option></select></div>
    <div><label>Turma</label>
      <select v-model="filtro.turma_id"><option value="">Todas</option>
        <option v-for="t in turmasFiltradas" :key="t.id" :value="t.id">{{ t.nome }}</option></select></div>
    <div><label>Disciplina</label>
      <select v-model="filtro.disciplina_id"><option value="">Todas</option>
        <option v-for="d in disciplinasFiltradas" :key="d.id" :value="d.id">{{ d.nome }}</option></select></div>
    <div><label>De</label><input type="date" v-model="filtro.inicio" /></div>
    <div><label>Até</label><input type="date" v-model="filtro.fim" /></div>
    <div><label title="Percentual mínimo da nota para considerar aprovado">Aprovação a partir de</label>
      <select v-model.number="filtro.corte"><option v-for="c in [50, 60, 70, 75]" :key="c" :value="c">{{ c }}% da nota</option></select></div>
  </div>

  <div v-if="erro" class="aviso erro">{{ erro }}</div>
  <p v-if="carregando && !dados" class="vazio">Calculando…</p>

  <template v-if="dados">
    <div v-if="!dados.resumo.provas_corrigidas" class="card vazio">
      Ainda não há provas enviadas nos filtros escolhidos. As análises aparecem assim que os alunos começarem a enviar as avaliações publicadas.
    </div>

    <template v-else>
      <!-- indicadores -->
      <div class="kpis">
        <div class="card kpi"><span class="sub">Avaliações</span><strong>{{ dados.resumo.avaliacoes }}</strong>
          <small class="sub">{{ dados.resumo.provas_corrigidas }} provas corrigidas</small></div>
        <div class="card kpi"><span class="sub">Média geral</span><strong>{{ fmt(dados.resumo.media) }}</strong>
          <small class="sub">da nota máxima</small></div>
        <div class="card kpi"><span class="sub">Aprovação</span><strong>{{ fmt(dados.resumo.aprovacao) }}</strong>
          <small class="sub">≥ {{ dados.corte }}% da nota</small></div>
        <div class="card kpi"><span class="sub">Participação</span><strong>{{ fmt(dados.resumo.participacao) }}</strong>
          <small class="sub">fizeram as provas encerradas</small></div>
        <div class="card kpi"><span class="sub">Alunos em atenção</span>
          <strong :class="{ alerta: dados.resumo.alunos_atencao }">{{ dados.resumo.alunos_atencao }}</strong>
          <small class="sub">de {{ dados.resumo.alunos }}</small></div>
      </div>

      <div class="grade2">
        <section class="card largo">
          <h2>Evolução da média por avaliação</h2>
          <p class="sub legenda">Média da turma em % da nota máxima, em ordem de aplicação. A linha tracejada é o corte de aprovação.</p>
          <Grafico v-if="evolucao" tipo="line" :dados="evolucao" :opcoes="opcoesPct" :altura="300" />
          <p v-else-if="muitasTurmas" class="vazio">Muitas turmas ao mesmo tempo: escolha uma escola ou turma no filtro para ver a evolução.</p>
          <details class="tabela-dados"><summary class="btn-link">Ver dados em tabela</summary>
            <table><thead><tr><th>Avaliação</th><th>Turma</th><th>Data</th><th class="num">Média</th><th class="num">Aprovação</th><th class="num">Enviadas</th></tr></thead>
              <tbody><tr v-for="a in dados.avaliacoes" :key="a.id"><td><router-link :to="`/avaliacoes/${a.id}/resultados`">{{ a.titulo }}</router-link></td>
                <td>{{ a.turma }}</td><td>{{ fmtData(a.data) }}</td><td class="num">{{ fmt(a.media) }}</td><td class="num">{{ fmt(a.aprovacao) }}</td>
                <td class="num">{{ a.enviadas }}/{{ a.matriculados }}</td></tr></tbody></table>
          </details>
        </section>

        <section v-if="comparativo" class="card">
          <h2>Comparativo entre turmas</h2>
          <p class="sub legenda">Média de todas as provas de cada turma. Passe o mouse para ver aprovação e participação.</p>
          <Grafico tipo="bar" :dados="comparativo" :opcoes="opcoesComparativo" :altura="Math.max(160, dados.turmas.length * 42)" />
        </section>

        <section class="card">
          <h2>Distribuição das notas</h2>
          <p class="sub legenda">Quantas provas caíram em cada faixa de desempenho.</p>
          <Grafico v-if="distribuicao" tipo="bar" :dados="distribuicao" :opcoes="opcoesDistribuicao" :altura="240" />
        </section>

        <section class="card">
          <h2>Objetivas × dissertativas</h2>
          <p class="sub legenda">Aproveitamento médio por tipo de questão.</p>
          <div class="kpis dois">
            <div class="kpi"><span class="sub">Objetivas</span><strong>{{ fmt(dados.tipos.objetiva) }}</strong>
              <div class="barra"><span :style="{ width: (dados.tipos.objetiva || 0) + '%' }"></span></div></div>
            <div class="kpi"><span class="sub">Dissertativas</span><strong>{{ fmt(dados.tipos.dissertativa) }}</strong>
              <div class="barra"><span :style="{ width: (dados.tipos.dissertativa || 0) + '%' }"></span></div></div>
          </div>
          <p class="sub dica" v-if="dados.tipos.objetiva != null && dados.tipos.dissertativa != null && Math.abs(dados.tipos.objetiva - dados.tipos.dissertativa) >= 15">
            💡 Diferença grande entre os tipos: {{ dados.tipos.objetiva > dados.tipos.dissertativa
              ? 'os alunos reconhecem a resposta, mas têm dificuldade para explicar com as próprias palavras.'
              : 'os alunos explicam bem, mas erram nas alternativas — vale revisar os distratores e a leitura atenta.' }}</p>
        </section>

        <section class="card largo">
          <h2>Conteúdos para retomar: questões com menor aproveitamento</h2>
          <p class="sub legenda">As 10 questões em que a turma foi pior. Passe o mouse para ver o enunciado e o erro mais comum.</p>
          <Grafico v-if="dificeis" tipo="bar" :dados="dificeis" :opcoes="opcoesDificeis" :altura="Math.max(200, dados.questoes_dificeis.length * 34)" />
          <table class="compacta">
            <thead><tr><th>Questão</th><th>Enunciado</th><th>Erro mais comum</th><th class="num">Aproveitamento</th></tr></thead>
            <tbody><tr v-for="q in dados.questoes_dificeis" :key="q.avaliacao_id + '-' + q.numero">
              <td><router-link :to="`/avaliacoes/${q.avaliacao_id}/resultados`">{{ q.avaliacao }} · Q{{ q.numero }}</router-link><br />
                <small class="sub">{{ q.turma }} · {{ q.tipo }}</small></td>
              <td>{{ q.enunciado }}</td>
              <td><small v-if="q.distrator">"{{ q.distrator.texto }}" — {{ q.distrator.percentual }}% marcaram</small><small v-else class="sub">—</small></td>
              <td class="num"><strong>{{ fmt(q.aproveitamento) }}</strong></td></tr></tbody>
          </table>
        </section>

        <section class="card largo">
          <div class="cabecalho" style="margin-bottom: .3rem">
            <div><h2>Mapa de notas</h2>
              <p class="sub legenda">Cada célula é a nota do aluno na avaliação (% da nota). Quanto mais escuro, melhor. "não fez" = faltou a uma prova já encerrada.</p></div>
            <div class="acoes nao-imprimir"><label style="margin: 0">Ordenar por</label>
              <select v-model="ordemAlunos" style="width: auto"><option value="media">menor média</option><option value="nome">nome</option></select></div>
          </div>
          <div class="tabela-rola">
            <table class="mapa">
              <thead><tr><th>Aluno</th><th class="num">Média</th>
                <th v-for="g in mapaAvs" :key="g.titulo" class="num" :title="g.titulo">{{ g.titulo }}</th></tr></thead>
              <tbody><tr v-for="al in alunosOrdenados" :key="al.id">
                <td>{{ al.nome }}</td><td class="num"><strong>{{ fmt(al.media) }}</strong></td>
                <td v-for="g in mapaAvs" :key="g.titulo" class="num cel" :style="notaEm(al, g).tem ? corCelula(notaEm(al, g).v) : {}">
                  <template v-if="notaEm(al, g).tem">{{ notaEm(al, g).v == null ? 'não fez' : Math.round(notaEm(al, g).v) }}</template>
                </td></tr></tbody>
            </table>
          </div>
        </section>

        <section class="card largo">
          <div class="cabecalho" style="margin-bottom: .3rem">
            <div><h2>Alunos que precisam de atenção</h2>
              <p class="sub legenda">Média abaixo do corte, queda de 20 pontos ou mais entre as duas últimas provas, provas não feitas ou muitas saídas da prova.</p></div>
            <label class="check nao-imprimir"><input type="checkbox" v-model="somenteAtencao" /> Só quem precisa de atenção</label>
          </div>
          <table v-if="alunosAtencao.length">
            <thead><tr><th>Aluno</th><th class="num">Média</th><th class="num">Tendência</th><th class="num">Não feitas</th><th class="num">Saídas</th><th>Motivos</th></tr></thead>
            <tbody><tr v-for="a in alunosAtencao" :key="a.id">
              <td>{{ a.nome }}<br /><small class="sub">{{ a.login }}</small></td>
              <td class="num"><strong>{{ fmt(a.media) }}</strong></td>
              <td class="num"><span v-if="a.tendencia != null" :class="a.tendencia < 0 ? 'queda' : 'alta'">
                {{ a.tendencia < 0 ? '▼' : '▲' }} {{ fmt(Math.abs(a.tendencia), ' p.p.') }}</span><span v-else class="sub">—</span></td>
              <td class="num">{{ a.faltas }}</td><td class="num">{{ a.saidas }}</td>
              <td><span v-for="m in a.atencao" :key="m" class="tag alerta" style="margin: 0 .25rem .25rem 0">⚠ {{ m }}</span>
                <span v-if="!a.atencao.length" class="tag ok">✓ ok</span></td></tr></tbody>
          </table>
          <p v-else class="vazio">Nenhum aluno em situação de atenção. 🎉</p>
        </section>
      </div>
    </template>
  </template>
</template>

<style scoped>
.filtros { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.kpis { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); margin-bottom: 1rem; }
.kpis.dois { grid-template-columns: 1fr 1fr; margin: .5rem 0 0; }
.kpi { display: flex; flex-direction: column; gap: .15rem; margin: 0; }
.kpi strong { font-size: 1.7rem; line-height: 1.2; font-variant-numeric: tabular-nums; }
.kpi strong.alerta { color: var(--alerta); }
.grade2 { display: grid; gap: 1rem; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grade2 > .card { margin: 0; min-width: 0; }
.largo { grid-column: 1 / -1; }
.legenda { margin: -.4rem 0 .8rem; font-size: .85rem; }
.dica { margin-top: .8rem; font-size: .88rem; }
.tabela-dados { margin-top: .6rem; }
.tabela-dados summary { cursor: pointer; }
table.compacta { margin-top: .8rem; font-size: .88rem; }
.mapa th { white-space: nowrap; font-size: .75rem; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
.mapa td { white-space: nowrap; }
.mapa td.cel { font-variant-numeric: tabular-nums; font-size: .85rem; border: 2px solid #fff; border-radius: 4px; }
.queda { color: var(--erro); font-weight: 600; }
.alta { color: var(--ok); font-weight: 600; }
@media (max-width: 800px) { .grade2 { grid-template-columns: 1fr; } }
@media print { .nao-imprimir, .topo { display: none !important; } .card { break-inside: avoid; } }
</style>
