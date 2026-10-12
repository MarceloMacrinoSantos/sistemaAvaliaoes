<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, fmtData, sessao } from '../../api'
import QrAcesso from '../../components/QrAcesso.vue'
const mostrarQr = ref(false)

const avaliacoes = ref([])
const escolas = ref([])
const turmas = ref([])
const disciplinas = ref([])
const filtro = ref({ escola_id: '', turma_id: '', disciplina_id: '' })
const erro = ref('')
const carregando = ref(true)

const STATUS = {
  rascunho: ['Rascunho', 'cinza'], agendada: ['Agendada', 'alerta'],
  em_andamento: ['Em andamento', 'ok'], encerrada: ['Encerrada', '']
}
const TIPO = { prova: 'Prova', simulado: 'Simulado', teste: 'Teste' }

const ehAdmin = computed(() => sessao.usuario?.papel === 'admin')
const disciplinasFiltradas = computed(() => {
  const vistos = new Set()
  return disciplinas.value.filter((d) => (!filtro.value.escola_id || !d.escola_id || d.escola_id === +filtro.value.escola_id)
    && !vistos.has(d.id) && vistos.add(d.id))
})
const turmasFiltradas = computed(() =>
  filtro.value.escola_id ? turmas.value.filter((t) => t.escola_id === +filtro.value.escola_id) : turmas.value)

async function carregar() {
  erro.value = ''
  const qs = new URLSearchParams(Object.entries(filtro.value).filter(([, v]) => v)).toString()
  try {
    avaliacoes.value = await api('/api/avaliacoes' + (qs ? '?' + qs : ''))
  } catch (e) { erro.value = e.message } finally { carregando.value = false }
}

onMounted(async () => {
  try {
    ;[escolas.value, turmas.value, disciplinas.value] = await Promise.all([
      api('/api/escolas'), api('/api/turmas'), api('/api/disciplinas')])
  } catch (e) { erro.value = e.message }
  carregar()
})
watch(filtro, carregar, { deep: true })

async function duplicar(av) {
  const nova = await api(`/api/avaliacoes/${av.id}/duplicar`, { method: 'POST' })
  avaliacoes.value.unshift(nova)
}

async function publicar(av) {
  if (!confirm(`Publicar "${av.titulo}"? Os alunos de ${av.turma} poderão fazê-la entre ${fmtData(av.inicio)} e ${fmtData(av.fim)}.`)) return
  try {
    const r = await api(`/api/avaliacoes/${av.id}/publicar`, { method: 'POST' })
    Object.assign(av, r)
  } catch (e) { erro.value = e.message }
}

async function excluir(av) {
  const aviso = av.qtd_tentativas ? `\n\nATENÇÃO: ${av.qtd_tentativas} aluno(s) já responderam; as respostas serão apagadas.` : ''
  if (!confirm(`Excluir "${av.titulo}"?${aviso}`)) return
  await api(`/api/avaliacoes/${av.id}`, { method: 'DELETE' })
  avaliacoes.value = avaliacoes.value.filter((a) => a.id !== av.id)
}
</script>

<template>
  <div class="cabecalho">
    <div>
      <h1>Avaliações</h1>
      <p class="sub">Provas, testes e simulados por escola, turma e disciplina.</p>
    </div>
    <div class="acoes">
      <button class="sec" @click="mostrarQr = true" title="Mostre na tela ou projete: os alunos escaneiam e entram">📱 QR code para os alunos</button>
      <router-link class="btn" to="/avaliacoes/nova">+ Nova avaliação</router-link>
    </div>
  </div>
  <QrAcesso v-if="mostrarQr" @fechar="mostrarQr = false" />

  <div v-if="erro" class="aviso erro">{{ erro }}</div>
  <div v-if="!carregando && !escolas.length" class="aviso info">
    <template v-if="ehAdmin">Comece cadastrando escolas, disciplinas e professores (com os vínculos) em
      <router-link to="/cadastros">Cadastros</router-link>.</template>
    <template v-else>Bem-vindo! Comece cadastrando sua escola, disciplinas, turmas e alunos em
      <router-link to="/cadastros">Cadastros</router-link>.</template>
  </div>
  <div v-else-if="!carregando && !turmas.length" class="aviso info">
    Crie sua primeira turma e importe os alunos em <router-link to="/cadastros">Cadastros</router-link>.
  </div>

  <div class="card linha">
    <div>
      <label>Escola</label>
      <select v-model="filtro.escola_id" @change="filtro.turma_id = ''">
        <option value="">Todas</option>
        <option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option>
      </select>
    </div>
    <div>
      <label>Turma</label>
      <select v-model="filtro.turma_id">
        <option value="">Todas</option>
        <option v-for="t in turmasFiltradas" :key="t.id" :value="t.id">{{ t.nome }} — {{ t.escola }}</option>
      </select>
    </div>
    <div>
      <label>Disciplina</label>
      <select v-model="filtro.disciplina_id">
        <option value="">Todas</option>
        <option v-for="d in disciplinasFiltradas" :key="d.id" :value="d.id">{{ d.nome }}</option>
      </select>
    </div>
  </div>

  <div class="card tabela-rola">
    <table v-if="avaliacoes.length">
      <thead>
        <tr><th>Avaliação</th><th>Turma</th><th>Período</th><th class="num">Questões</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="av in avaliacoes" :key="av.id">
          <td>
            <strong>{{ av.titulo }}</strong><br />
            <small class="sub">{{ TIPO[av.tipo] }} · {{ av.disciplina }}</small>
          </td>
          <td>{{ av.turma }}<br /><small class="sub">{{ av.escola }}<span v-if="ehAdmin && av.professor"> · {{ av.professor }}</span></small></td>
          <td><small>{{ fmtData(av.inicio) }}<br />até {{ fmtData(av.fim) }}</small></td>
          <td class="num">{{ av.qtd_questoes }}<br /><small class="sub">{{ av.pontuacao_total }} pts</small></td>
          <td><span class="tag" :class="STATUS[av.status][1]">{{ STATUS[av.status][0] }}</span>
            <br v-if="av.status === 'rascunho'" /><small v-if="av.status === 'rascunho'" class="sub">alunos ainda não veem</small></td>
          <td>
            <div class="acoes" style="justify-content: flex-end">
              <button v-if="av.status === 'rascunho'" class="pequeno publicar" :disabled="!av.qtd_questoes"
                :title="av.qtd_questoes ? 'Os alunos da turma passam a ver a avaliação' : 'Adicione questões antes'" @click="publicar(av)">▶ Publicar</button>
              <router-link class="btn sec pequeno" :to="`/avaliacoes/${av.id}`">Editar</router-link>
              <router-link class="btn pequeno" :to="`/avaliacoes/${av.id}/resultados`">
                Resultados ({{ av.qtd_tentativas }})
              </router-link>
              <button class="sec pequeno" title="Duplicar para outra turma" @click="duplicar(av)">Duplicar</button>
              <button class="perigo pequeno" @click="excluir(av)">Excluir</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else-if="!carregando" class="vazio">Nenhuma avaliação encontrada.</div>
  </div>
</template>

<style scoped>
.publicar { background: var(--ok); border-color: var(--ok); }
.publicar:hover { background: #146a3e; }
</style>
