<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import TextoComImagens from '../../components/TextoComImagens.vue'
import { api, baixar, fmtData, fmtDuracao } from '../../api'
import Feedback from '../../components/Feedback.vue'
import Monitoramento from '../../components/Monitoramento.vue'

const props = defineProps({ id: String })
const dados = ref(null)
const erro = ref('')
const aba = ref('alunos')
const detalhe = ref(null)
const revisao = ref(null)
let timer = null

const SIT = { nao_iniciou: ['Não iniciou', 'cinza'], respondendo: ['Respondendo…', 'alerta'], enviada: ['Enviada', 'ok'] }
const LIB = { apos_fim: 'após o encerramento', apos_envio: 'logo após o envio', manual: 'manualmente' }
const fmt = (n) => (n == null ? '—' : (Math.round(n * 100) / 100).toLocaleString('pt-BR'))
const comOcorrencia = computed(() => dados.value?.alunos.filter((a) => a.monitoramento?.alerta).length || 0)
const respondendo = computed(() => dados.value?.alunos.filter((a) => a.situacao === 'respondendo').length || 0)

async function carregar() {
  try { dados.value = await api(`/api/avaliacoes/${props.id}/resultados`) } catch (e) { erro.value = e.message }
}
onMounted(() => {
  carregar()
  timer = setInterval(() => { if (!detalhe.value && !revisao.value && !monitAoVivo.value) carregar() }, 15000) // acompanhamento ao vivo
})
onUnmounted(() => clearInterval(timer))

const monitAoVivo = ref(null)
async function abrirMonit(l) {
  monitAoVivo.value = { nome: l.nome, m: (await api(`/api/tentativas/${l.tentativa_id}/monitoramento`)) }
}
async function abrir(l) {
  detalhe.value = await api(`/api/tentativas/${l.tentativa_id}`)
}
function revisar(q) {
  revisao.value = { resposta_id: q.resposta_id, pontos: q.pontos, max: q.pontos_max, comentario: q.comentario_professor || '' }
}
async function salvarRevisao() {
  try {
    const p = revisao.value.pontos === '' || revisao.value.pontos == null ? null
      : Math.min(revisao.value.max, Math.round(+String(revisao.value.pontos).replace(',', '.') * 100) / 100)
    await api(`/api/respostas/${revisao.value.resposta_id}/revisar`, {
      method: 'PUT', body: { pontos: p, comentario: revisao.value.comentario || null }
    })
    revisao.value = null
    detalhe.value = await api(`/api/tentativas/${detalhe.value.tentativa_id}`)
    carregar()
  } catch (e) { alert(e.message) }
}
async function liberar(v) {
  await api(`/api/avaliacoes/${props.id}/liberar-resultado?liberar=${v}`, { method: 'POST' })
  carregar()
}
async function encerrar() {
  if (!confirm('Encerrar agora? Todas as provas em andamento serão enviadas e corrigidas automaticamente.')) return
  await api(`/api/avaliacoes/${props.id}/encerrar`, { method: 'POST' })
  carregar()
}
async function reabrir(l) {
  if (!confirm(`Apagar a tentativa de ${l.nome} para que ele(a) possa refazer? As respostas serão perdidas.`)) return
  await api(`/api/tentativas/${l.tentativa_id}`, { method: 'DELETE' })
  carregar()
}
</script>

<template>
  <div v-if="erro" class="aviso erro">{{ erro }}</div>
  <template v-if="dados">
    <div class="cabecalho">
      <div>
        <router-link to="/painel" class="sub">← Avaliações</router-link>
        <h1>{{ dados.avaliacao.titulo }}</h1>
        <p class="sub">{{ dados.avaliacao.turma }} · {{ dados.avaliacao.escola }} · {{ dados.avaliacao.disciplina }}
          · {{ fmtData(dados.avaliacao.inicio) }} a {{ fmtData(dados.avaliacao.fim) }}</p>
      </div>
      <div class="acoes">
        <router-link class="btn sec" :to="`/avaliacoes/${id}`">Editar</router-link>
        <button class="sec" @click="baixar(`/api/avaliacoes/${id}/resultados.csv`, `resultados_${id}.csv`)">Exportar planilha</button>
        <button v-if="dados.avaliacao.status === 'em_andamento'" class="perigo" @click="encerrar">Encerrar agora</button>
      </div>
    </div>

    <div class="grade" style="margin-bottom: 1rem">
      <div class="card"><div class="sub">Enviadas</div><div class="big">{{ dados.resumo.enviadas }} / {{ dados.resumo.total_alunos }}</div>
        <small v-if="respondendo" class="sub">{{ respondendo }} respondendo agora</small>
        <small v-if="comOcorrencia" class="sub" style="display: block; color: var(--alerta)">⚠ {{ comOcorrencia }} aluno(s) saíram da prova</small></div>
      <div class="card"><div class="sub">Média da turma</div><div class="big">{{ fmt(dados.resumo.media) }}
        <small class="sub">/ {{ dados.avaliacao.pontuacao_total }}</small></div></div>
      <div class="card"><div class="sub">Maior / menor nota</div><div class="big">{{ fmt(dados.resumo.maior) }} / {{ fmt(dados.resumo.menor) }}</div></div>
      <div class="card">
        <div class="sub">Feedback para os alunos</div>
        <div style="margin: .25rem 0 .5rem">
          <span class="tag" :class="dados.resumo.resultado_visivel_para_alunos ? 'ok' : 'cinza'">
            {{ dados.resumo.resultado_visivel_para_alunos ? 'Liberado' : 'Ainda não liberado' }}</span>
          <small class="sub"> (regra: {{ LIB[dados.avaliacao.liberar_resultado] }})</small>
        </div>
        <button v-if="!dados.avaliacao.resultado_liberado && !dados.resumo.resultado_visivel_para_alunos" class="pequeno" @click="liberar(true)">Liberar agora</button>
        <button v-else-if="dados.avaliacao.resultado_liberado" class="sec pequeno" @click="liberar(false)">Desfazer liberação manual</button>
      </div>
    </div>

    <div class="abas">
      <button :class="{ ativa: aba === 'alunos' }" @click="aba = 'alunos'">Por aluno</button>
      <button :class="{ ativa: aba === 'questoes' }" @click="aba = 'questoes'">Por questão</button>
    </div>

    <div v-if="aba === 'alunos'" class="card tabela-rola">
      <table>
        <thead><tr><th>Aluno</th><th>Situação</th><th>Monitoramento</th><th>Enviado em</th><th class="num">Nota</th><th></th></tr></thead>
        <tbody>
          <tr v-for="l in dados.alunos" :key="l.aluno_id">
            <td>{{ l.nome }}<br /><small class="sub">{{ l.login }}</small></td>
            <td>
              <span class="tag" :class="SIT[l.situacao][1]">{{ SIT[l.situacao][0] }}</span>
              <span v-if="l.envio_automatico" class="tag cinza" title="Enviada ao fim do tempo">auto</span>
              <span v-if="l.dissertativas_nao_revisadas" class="tag alerta" title="Dissertativas com nota automática ainda não revisada">revisar</span>
            </td>
            <td>
              <template v-if="l.monitoramento">
                <span v-if="!l.monitoramento.alerta" class="tag ok">sem saídas</span>
                <span v-if="l.monitoramento.qtd_saidas" class="tag alerta"
                  :title="`Tempo fora: ${fmtDuracao(l.monitoramento.tempo_fora_seg)}`">
                  ↗ {{ l.monitoramento.qtd_saidas }} saída(s) · {{ fmtDuracao(l.monitoramento.tempo_fora_seg) }}</span>
                <span v-if="l.monitoramento.qtd_fechamentos" class="tag alerta">✕ fechou {{ l.monitoramento.qtd_fechamentos }}x</span>
                <span v-if="l.monitoramento.outro_dispositivo" class="tag erro">⚠ outro dispositivo</span>
                <br /><small class="sub">{{ l.monitoramento.navegador_inicio }} · {{ l.monitoramento.ip_inicio }}</small>
              </template>
              <span v-else class="sub">—</span>
            </td>
            <td><small>{{ fmtData(l.enviado_em) }}</small></td>
            <td class="num"><strong>{{ fmt(l.nota) }}</strong></td>
            <td class="num"><div class="acoes" style="justify-content: flex-end">
              <button v-if="l.situacao === 'enviada'" class="pequeno" @click="abrir(l)">Ver correção</button>
              <button v-else-if="l.situacao === 'respondendo'" class="sec pequeno" @click="abrirMonit(l)">Acompanhar</button>
              <button v-if="l.tentativa_id" class="perigo pequeno" title="Permitir refazer" @click="reabrir(l)">Reabrir</button>
            </div></td>
          </tr>
        </tbody>
      </table>
      <p v-if="!dados.alunos.length" class="vazio">Nenhum aluno na turma.</p>
    </div>

    <div v-else>
      <div v-for="q in dados.questoes" :key="q.questao_id" class="card">
        <div class="cabecalho" style="margin-bottom: .4rem">
          <strong>{{ q.numero }}. {{ q.enunciado }}</strong>
          <span class="tag" :class="q.percentual_acerto == null ? 'cinza' : q.percentual_acerto >= 60 ? 'ok' : q.percentual_acerto >= 30 ? 'alerta' : 'erro'">
            {{ q.percentual_acerto == null ? 'sem respostas' : q.percentual_acerto + '% de acerto' }}</span>
        </div>
        <div class="barra"><span :style="{ width: (q.percentual_acerto || 0) + '%' }"></span></div>
        <small class="sub">{{ q.acertos }} de {{ q.respostas }} acertaram · média {{ fmt(q.media_pontos) }} / {{ q.pontos }} pt</small>
        <table v-if="q.distribuicao" style="margin-top: .5rem">
          <tr v-for="(d, i) in q.distribuicao" :key="i">
            <td :style="d.correta ? 'color: var(--ok); font-weight: 600' : ''">{{ 'ABCDEFGHIJ'[i] }}) <TextoComImagens tag="span" :texto="d.texto" /> <span v-if="d.correta">✓</span></td>
            <td class="num" style="width: 120px">{{ d.qtd }} aluno(s)</td>
          </tr>
        </table>
      </div>
    </div>
  </template>

  <!-- correção individual -->
  <div v-if="detalhe" class="modal-fundo" @click.self="detalhe = null">
    <div class="modal">
      <div class="cabecalho">
        <div><h2 style="margin: 0">{{ detalhe.aluno.nome }}</h2><small class="sub">Enviado em {{ fmtData(detalhe.enviado_em) }}</small></div>
        <button class="sec" @click="detalhe = null">Fechar</button>
      </div>
      <Feedback :dados="detalhe" revisavel @revisar="revisar" />
    </div>
  </div>

  <div v-if="monitAoVivo" class="modal-fundo" @click.self="monitAoVivo = null">
    <div class="modal">
      <div class="cabecalho"><h2 style="margin: 0">{{ monitAoVivo.nome }} — respondendo</h2>
        <button class="sec" @click="monitAoVivo = null">Fechar</button></div>
      <Monitoramento :m="monitAoVivo.m" professor />
    </div>
  </div>

  <div v-if="revisao" class="modal-fundo" style="z-index: 60">
    <form class="modal" style="max-width: 440px" @submit.prevent="salvarRevisao">
      <h2>Revisar questão</h2>
      <div class="campo"><label>Pontos (máx. {{ fmt(revisao.max) }})</label>
        <input type="number" step="any" min="0" :max="revisao.max" v-model="revisao.pontos" /></div>
      <div class="acoes" style="margin: -.3rem 0 .8rem">
        <button type="button" class="sec pequeno" @click="revisao.pontos = revisao.max">Nota cheia ({{ fmt(revisao.max) }})</button>
        <button type="button" class="sec pequeno" @click="revisao.pontos = Math.round(revisao.max * 50) / 100">Metade</button>
        <button type="button" class="sec pequeno" @click="revisao.pontos = 0">Zero</button>
      </div>
      <div class="campo"><label>Comentário para o aluno</label><textarea v-model="revisao.comentario" rows="3"></textarea></div>
      <div class="acoes"><button>Salvar</button><button type="button" class="sec" @click="revisao = null">Cancelar</button></div>
    </form>
  </div>
</template>

<style scoped>
.big { font-size: 1.6rem; font-weight: 700; }
</style>
