<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import TextoComImagens from '../../components/TextoComImagens.vue'
import { useRouter } from 'vue-router'
import { api, fmtData, fmtDuracao, sessao } from '../../api'

const props = defineProps({ id: String })
const router = useRouter()

const prova = ref(null)
const erro = ref('')
const atual = ref(0)
const respostas = reactive({})          // questao_id -> { alternativa_id, texto }
const pendentes = reactive(new Set())   // questões com alteração ainda não salva
const statusSalvar = ref('salvo')       // salvo | salvando | offline
const restante = ref(null)              // segundos
const revisando = ref(false)
const enviando = ref(false)
const enviada = ref(null)
let offset = 0, relogio = null, retentativa = null
const debounces = {}

// ---------------- monitoramento (troca de aba, saída da janela, fechamento) ----------------
const monit = reactive({ qtd_saidas: 0, tempo_fora_seg: 0, qtd_fechamentos: 0, qtd_acessos: 1, outro_dispositivo: false })
const alertaVolta = ref(null)     // { duracao, numero } — mostrado ao aluno quando ele volta
const avisoReabertura = ref('')
let fora = null                   // saída em andamento
let filaEventos = [], enviandoEventos = false, retryEventos = null
const LIMIAR_MS = 1000            // saídas com menos de 1 s (piscadas do sistema) são ignoradas

const monitorando = () => prova.value?.monitorar && !enviando.value && !enviada.value

function registrar(ev) {
  filaEventos.push({ ...ev, em: new Date(Date.now() + offset).toISOString() })
  enviarEventos()
}
async function enviarEventos() {
  if (enviandoEventos || !filaEventos.length || !prova.value) return
  enviandoEventos = true
  const lote = filaEventos.splice(0)
  try {
    const r = await api(`/api/aluno/tentativas/${prova.value.tentativa_id}/eventos`, { method: 'POST', body: { eventos: lote } })
    Object.assign(monit, r)
  } catch {
    filaEventos.unshift(...lote)   // sem internet: guarda e tenta de novo
    clearTimeout(retryEventos)
    retryEventos = setTimeout(enviarEventos, 5000)
  } finally { enviandoEventos = false }
  if (filaEventos.length) enviarEventos()
}
function sair(tipo) {
  if (!monitorando() || fora) return
  fora = { tipo, desde: Date.now(), registrado: false }
  fora.timer = setTimeout(() => {
    fora.registrado = true
    monit.qtd_saidas++
    registrar({ tipo })
  }, LIMIAR_MS)
}
function voltar() {
  if (!fora || document.hidden || !document.hasFocus()) return
  clearTimeout(fora.timer)
  if (fora.registrado) {
    const duracao = Math.max(1, Math.round((Date.now() - fora.desde) / 1000))
    monit.tempo_fora_seg += duracao
    registrar({ tipo: 'voltou', duracao_seg: duracao })
    alertaVolta.value = { duracao, numero: monit.qtd_saidas, tipo: fora.tipo }
  }
  fora = null
}
const aoMudarVisibilidade = () => (document.hidden ? sair('saiu_aba') : voltar())
const aoPerderFoco = () => { if (!document.hidden) sair('saiu_janela') }
function aoFecharPagina() {
  if (!monitorando()) return
  // keepalive garante o envio mesmo com a página sendo fechada
  const eventos = [...filaEventos.splice(0), { tipo: 'fechou', em: new Date(Date.now() + offset).toISOString() }]
  try {
    fetch(`/api/aluno/tentativas/${prova.value.tentativa_id}/eventos`, {
      method: 'POST', keepalive: true,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessao.token}` },
      body: JSON.stringify({ eventos })
    })
  } catch {}
}
function ligarMonitoramento() {
  document.addEventListener('visibilitychange', aoMudarVisibilidade)
  window.addEventListener('blur', aoPerderFoco)
  window.addEventListener('focus', voltar)
  window.addEventListener('pagehide', aoFecharPagina)
}
function desligarMonitoramento() {
  document.removeEventListener('visibilitychange', aoMudarVisibilidade)
  window.removeEventListener('blur', aoPerderFoco)
  window.removeEventListener('focus', voltar)
  window.removeEventListener('pagehide', aoFecharPagina)
  if (fora) clearTimeout(fora.timer)
  clearTimeout(retryEventos)
}

const LETRAS = 'ABCDEFGHIJ'
const q = computed(() => prova.value?.questoes[atual.value])
const respondida = (qq) => {
  const r = respostas[qq.id]
  return qq.tipo === 'objetiva' ? r?.alternativa_id != null : !!r?.texto?.trim()
}
const qtdRespondidas = computed(() => prova.value?.questoes.filter(respondida).length || 0)
const emBranco = computed(() => prova.value?.questoes.filter((x) => !respondida(x)) || [])
const tempoFmt = computed(() => {
  if (restante.value == null) return ''
  const s = Math.max(0, restante.value)
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60
  return (h ? h + ':' : '') + String(m).padStart(2, '0') + ':' + String(ss).padStart(2, '0')
})

function avisoSaida(e) {
  if (pendentes.size) { e.preventDefault(); e.returnValue = '' }
}

onMounted(async () => {
  try {
    const p = await api(`/api/aluno/avaliacoes/${props.id}/iniciar`, {
      method: 'POST', body: { tela: `${screen.width}x${screen.height}` }
    })
    offset = new Date(p.agora).getTime() - Date.now() // sincroniza com o relógio do servidor
    for (const qq of p.questoes) respostas[qq.id] = { alternativa_id: null, texto: '', ...(p.respostas[qq.id] || {}) }
    prova.value = p
    Object.assign(monit, p.monitoramento || {})
    if (p.monitorar && monit.qtd_acessos > 1) {
      avisoReabertura.value = monit.outro_dispositivo
        ? 'Detectamos que a avaliação foi aberta em outro navegador ou dispositivo. Isso foi registrado e o professor será informado.'
        : 'Você saiu e reabriu a avaliação (a página foi fechada ou recarregada). Isso foi registrado.'
    }
    if (p.monitorar) ligarMonitoramento()
    tick()
    relogio = setInterval(tick, 1000)
    window.addEventListener('beforeunload', avisoSaida)
  } catch (e) {
    if (e.status === 409) return router.replace('/aluno')
    erro.value = e.message
  }
})
onUnmounted(() => {
  desligarMonitoramento()
  clearInterval(relogio)
  clearTimeout(retentativa)
  window.removeEventListener('beforeunload', avisoSaida)
})

function tick() {
  restante.value = Math.round((new Date(prova.value.prazo).getTime() - (Date.now() + offset)) / 1000)
  if (restante.value <= 0 && !enviando.value && !enviada.value) enviar(true)
}

async function salvar(qid) {
  const r = respostas[qid]
  statusSalvar.value = 'salvando'
  try {
    await api(`/api/aluno/tentativas/${prova.value.tentativa_id}/respostas`, {
      method: 'PUT', body: { questao_id: qid, alternativa_id: r.alternativa_id, texto: r.texto }
    })
    pendentes.delete(qid)
    if (!pendentes.size) statusSalvar.value = 'salvo'
  } catch (e) {
    if (e.status === 409) { // tempo acabou no servidor
      pendentes.clear()
      return finalizar()
    }
    statusSalvar.value = 'offline'
    clearTimeout(retentativa)
    retentativa = setTimeout(salvarPendentes, 4000) // tenta de novo sozinho
  }
}
async function salvarPendentes() {
  for (const qid of [...pendentes]) await salvar(qid)
}

function marcar(alt) {
  respostas[q.value.id].alternativa_id = alt.id
  pendentes.add(q.value.id)
  salvar(q.value.id)
}
function digitar(qid) {
  pendentes.add(qid)
  statusSalvar.value = 'salvando'
  clearTimeout(debounces[qid])
  debounces[qid] = setTimeout(() => salvar(qid), 1200)
}

async function enviar(automatico = false) {
  if (enviando.value) return
  enviando.value = true
  Object.values(debounces).forEach(clearTimeout)
  await salvarPendentes()
  await enviarEventos()
  await finalizar(automatico)
}
async function finalizar(automatico = true) {
  enviando.value = true
  try {
    const r = await api(`/api/aluno/tentativas/${prova.value.tentativa_id}/enviar`, { method: 'POST' })
    clearInterval(relogio)
    desligarMonitoramento()
    window.removeEventListener('beforeunload', avisoSaida)
    if (r.resultado_disponivel) return router.replace(`/aluno/resultado/${prova.value.tentativa_id}`)
    enviada.value = { ...r, automatico }
  } catch (e) {
    enviando.value = false
    if (!e.offline) { erro.value = e.message; return }
    statusSalvar.value = 'offline'
    setTimeout(() => finalizar(automatico), 4000) // sem internet: tenta de novo
  }
}
</script>

<template>
  <div v-if="erro" class="card">
    <div class="aviso erro">{{ erro }}</div>
    <router-link to="/aluno">← Voltar</router-link>
  </div>

  <div v-else-if="enviada" class="card" style="text-align: center; padding: 2.5rem 1rem">
    <div style="font-size: 3rem">✅</div>
    <h1>Avaliação enviada!</h1>
    <p v-if="enviada.automatico" class="sub">O tempo terminou e suas respostas foram enviadas automaticamente.</p>
    <p class="sub">Suas respostas foram corrigidas. A nota e o feedback de cada questão ficarão disponíveis
      após o encerramento da avaliação<span v-if="enviada.fim_avaliacao"> ({{ fmtData(enviada.fim_avaliacao) }})</span>.</p>
    <p v-if="prova?.monitorar" class="sub">🔒 Monitoramento: {{ monit.qtd_saidas }} saída(s) da prova
      ({{ fmtDuracao(monit.tempo_fora_seg) }} fora)<span v-if="monit.qtd_fechamentos">, {{ monit.qtd_fechamentos }} fechamento(s) da página</span>.</p>
        <router-link class="btn" to="/aluno">Voltar para minhas avaliações</router-link>
  </div>

  <template v-else-if="prova">
    <div class="barra-prova card">
      <div style="min-width: 0">
        <strong class="titulo">{{ prova.titulo }}</strong>
        <small class="sub">{{ qtdRespondidas }} de {{ prova.questoes.length }} respondidas ·
          <span v-if="statusSalvar === 'salvo'" style="color: var(--ok)">✓ salvo</span>
          <span v-else-if="statusSalvar === 'salvando'">salvando…</span>
          <span v-else style="color: var(--erro)">⚠ sem conexão — tentando salvar</span>
        </small>
      </div>
      <div class="tempo" :class="{ urgente: restante < 300 }" title="Tempo restante">⏱ {{ tempoFmt }}</div>
    </div>

    <div v-if="prova.monitorar" class="aviso monitorada" :class="{ alerta: monit.qtd_saidas || monit.qtd_fechamentos }">
      🔒 <strong>Avaliação monitorada.</strong> Trocas de aba, saídas da janela e fechamento da página são registrados
      e informados ao professor.
      <span v-if="monit.qtd_saidas || monit.qtd_fechamentos"><br />Registrado até agora:
        {{ monit.qtd_saidas }} saída(s), {{ fmtDuracao(monit.tempo_fora_seg) }} fora<span v-if="monit.qtd_fechamentos">,
        {{ monit.qtd_fechamentos }} fechamento(s)</span>.</span>
    </div>
    <div v-if="avisoReabertura" class="aviso alerta">⚠ {{ avisoReabertura }}
      <button class="btn-link" style="margin-left: .5rem" @click="avisoReabertura = ''">ok</button></div>
    <div v-if="prova.descricao && atual === 0 && !revisando" class="aviso info">{{ prova.descricao }}</div>

    <nav class="mapa">
      <button v-for="(qq, i) in prova.questoes" :key="qq.id" class="pequeno"
        :class="{ sec: i !== atual || revisando, feita: respondida(qq) }" @click="atual = i; revisando = false">
        {{ i + 1 }}
      </button>
    </nav>

    <!-- revisão final -->
    <div v-if="revisando" class="card">
      <h2>Revisar e enviar</h2>
      <p>Você respondeu <strong>{{ qtdRespondidas }}</strong> de <strong>{{ prova.questoes.length }}</strong> questões.</p>
      <div v-if="emBranco.length" class="aviso alerta">
        Questões em branco: {{ emBranco.map((x) => x.numero).join(', ') }}. Clique no número acima para respondê-las.
      </div>
      <p class="sub">Depois de enviar não será possível alterar as respostas.</p>
      <div class="acoes">
        <button :disabled="enviando" @click="enviar(false)">{{ enviando ? 'Enviando…' : 'Enviar avaliação' }}</button>
        <button class="sec" @click="revisando = false">Continuar respondendo</button>
      </div>
    </div>

    <!-- questão atual -->
    <div v-else-if="q" class="card">
      <div class="cabecalho" style="margin-bottom: .5rem">
        <strong>Questão {{ atual + 1 }} de {{ prova.questoes.length }}</strong>
        <small class="sub">{{ q.pontos }} ponto(s)</small>
      </div>
      <TextoComImagens tag="div" class="enunciado" style="font-size: 1.05rem" :texto="q.enunciado" />

      <div v-if="q.tipo === 'objetiva'">
        <button v-for="(a, i) in q.alternativas" :key="a.id" type="button" class="alternativa"
          :class="{ marcada: respostas[q.id].alternativa_id === a.id }" style="width: 100%; text-align: left"
          @click="marcar(a)">
          <span class="letra">{{ LETRAS[i] }})</span><TextoComImagens tag="span" style="flex: 1; white-space: normal" :texto="a.texto" />
        </button>
      </div>
      <div v-else>
        <textarea v-model="respostas[q.id].texto" rows="8" placeholder="Escreva sua resposta aqui…"
          @input="digitar(q.id)" @blur="pendentes.has(q.id) && salvar(q.id)"></textarea>
      </div>

      <div class="acoes" style="justify-content: space-between; margin-top: 1rem">
        <button class="sec" :disabled="atual === 0" @click="atual--">← Anterior</button>
        <button v-if="atual < prova.questoes.length - 1" @click="atual++">Próxima →</button>
        <button v-else @click="revisando = true">Revisar e enviar</button>
      </div>
    </div>
    <p style="text-align: right"><button class="btn-link" @click="revisando = true">Finalizar avaliação</button></p>
  </template>

  <p v-else class="vazio">Carregando avaliação…</p>

  <!-- alerta mostrado quando o aluno volta depois de sair da prova -->
  <div v-if="alertaVolta" class="modal-fundo" style="align-items: center">
    <div class="modal" style="max-width: 440px; text-align: center">
      <div style="font-size: 2.4rem">⚠️</div>
      <h2>Você saiu da avaliação</h2>
      <p>{{ alertaVolta.tipo === 'saiu_aba' ? 'Você trocou de aba ou minimizou o navegador' : 'Você clicou em outra janela ou programa' }}
        e ficou <strong>{{ fmtDuracao(alertaVolta.duracao) }}</strong> fora.</p>
      <p>Esta é a sua <strong>{{ alertaVolta.numero }}ª saída</strong>. O registro foi enviado ao professor.</p>
      <button @click="alertaVolta = null" style="justify-content: center; width: 100%">Entendi, voltar para a prova</button>
    </div>
  </div>
</template>

<style scoped>
.barra-prova { display: flex; justify-content: space-between; align-items: center; gap: 1rem; position: sticky; top: 52px; z-index: 5; }
.barra-prova .titulo { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tempo { font-size: 1.35rem; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tempo.urgente { color: var(--erro); }
.aviso.monitorada { background: #eef1f6; color: var(--texto); font-size: .88rem; }
.aviso.monitorada.alerta { background: var(--alerta-claro); color: var(--alerta); }
.mapa { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: 1rem; }
.mapa button { min-width: 2.4rem; justify-content: center; }
.mapa button.sec.feita { background: var(--ok-claro); border-color: var(--ok); color: var(--ok); }
</style>
