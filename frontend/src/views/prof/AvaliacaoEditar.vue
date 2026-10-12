<script setup>
import { computed, onMounted, ref } from 'vue'
import TextoComImagens from '../../components/TextoComImagens.vue'
import EditorTexto from '../../components/EditorTexto.vue'
import { useRouter } from 'vue-router'
import { api, deInputLocal, paraInputLocal } from '../../api'
import ImportarQuestoes from '../../components/ImportarQuestoes.vue'

const props = defineProps({ id: String })
const router = useRouter()

const escolas = ref([])
const turmas = ref([])
const disciplinas = ref([])
const msg = ref({ tipo: '', texto: '' })
const salvando = ref(false)

const hoje = new Date()
const form = ref({
  titulo: '', descricao: '', tipo: 'prova', escola_id: '', turma_id: '', disciplina_id: '',
  inicio: paraInputLocal(hoje.toISOString()),
  fim: paraInputLocal(new Date(hoje.getTime() + 2 * 3600e3).toISOString()),
  duracao_min: 60, embaralhar_questoes: true, embaralhar_alternativas: true,
  liberar_resultado: 'apos_fim', publicada: false,
  nota_total: 10, peso_objetiva: 1, peso_dissertativa: 2, monitorar: true
})
const questoes = ref([])
const qtdTentativas = ref(0)
const bloqueada = computed(() => qtdTentativas.value > 0)
const totalPontos = computed(() => Math.round(questoes.value.reduce((s, q) => s + q.pontos, 0) * 100) / 100)
const fmt = (n) => (Math.round(n * 100) / 100).toLocaleString('pt-BR')

// ----- distribuição da nota pelos pesos -----
const pesosEditados = ref({})        // questao_id -> peso digitado
const pesoDe = (q) => pesosEditados.value[q.id] ?? q.peso
const somaPesos = computed(() => questoes.value.reduce((s, q) => s + (+pesoDe(q) || 0), 0))
const valorPrevisto = (q) => somaPesos.value ? (form.value.nota_total * (+pesoDe(q) || 0)) / somaPesos.value : 0
const pesosAlterados = computed(() => questoes.value.some((q) => pesosEditados.value[q.id] != null && +pesosEditados.value[q.id] !== q.peso))
const somaPorTipo = (tipo) => questoes.value.filter((q) => q.tipo === tipo).reduce((s, q) => s + valorPrevisto(q), 0)
// alerta se alguma dissertativa não vale mais que as objetivas
const alertaPeso = computed(() => {
  const obj = questoes.value.filter((q) => q.tipo === 'objetiva').map((q) => +pesoDe(q))
  const dis = questoes.value.filter((q) => q.tipo === 'dissertativa').map((q) => +pesoDe(q))
  return obj.length && dis.length && Math.min(...dis) <= Math.max(...obj)
})
async function salvarPesos() {
  const pesos = {}
  for (const q of questoes.value) pesos[q.id] = +pesoDe(q)
  if (Object.values(pesos).some((p) => !(p > 0))) return avisar('Todos os pesos devem ser maiores que zero.', 'erro')
  try {
    const av = await api(`/api/avaliacoes/${props.id}/pesos`, { method: 'PUT', body: { pesos } })
    questoes.value = av.questoes
    pesosEditados.value = {}
    avisar('Pesos salvos. A nota foi redistribuída entre as questões.')
  } catch (e) { avisar(e.message, 'erro') }
}
async function aplicarPadrao() {
  if (!confirm(`Aplicar peso ${form.value.peso_objetiva} a todas as objetivas e ${form.value.peso_dissertativa} a todas as dissertativas?`)) return
  try {
    await salvar()
    const av = await api(`/api/avaliacoes/${props.id}/pesos-padrao`, { method: 'POST' })
    questoes.value = av.questoes
    pesosEditados.value = {}
  } catch (e) { avisar(e.message, 'erro') }
}
const turmasDaEscola = computed(() => turmas.value.filter((t) => t.escola_id === +form.value.escola_id))
const disciplinasDaEscola = computed(() => {
  const vistos = new Set()
  return disciplinas.value.filter((d) => (!d.escola_id || d.escola_id === +form.value.escola_id) && !vistos.has(d.id) && vistos.add(d.id))
})

// editor de questão
const LETRAS = 'ABCDEFGHIJ'
const qForm = ref(null)
const importando = ref(false)
function aoImportar({ av, qtd }) {
  questoes.value = av.questoes
  pesosEditados.value = {}
  importando.value = false
  avisar(`${qtd} questão(ões) importada(s). A nota foi redistribuída pelos pesos — confira abaixo.`)
}
function novaQuestao(tipo) {
  qForm.value = {
    id: null, tipo, enunciado: '', peso: tipo === 'dissertativa' ? form.value.peso_dissertativa : form.value.peso_objetiva, explicacao: '', gabarito_texto: '', palavras_chave_txt: '',
    alternativas: tipo === 'objetiva' ? [0, 1, 2, 3].map((i) => ({ texto: '', correta: i === 0 })) : []
  }
}
function editarQuestao(q) {
  qForm.value = {
    ...q, explicacao: q.explicacao || '', gabarito_texto: q.gabarito_texto || '',
    palavras_chave_txt: (q.palavras_chave || []).join('\n'),
    alternativas: q.alternativas.map((a) => ({ texto: a.texto, correta: a.correta }))
  }
}
function marcarCorreta(i) { qForm.value.alternativas.forEach((a, j) => (a.correta = i === j)) }

function avisar(texto, tipo = 'ok') { msg.value = { texto, tipo }; window.scrollTo({ top: 0, behavior: 'smooth' }) }

onMounted(async () => {
  ;[escolas.value, turmas.value, disciplinas.value] = await Promise.all([
    api('/api/escolas'), api('/api/turmas'), api('/api/disciplinas')])
  if (props.id) {
    const av = await api(`/api/avaliacoes/${props.id}`)
    Object.assign(form.value, {
      ...av, descricao: av.descricao || '', inicio: paraInputLocal(av.inicio), fim: paraInputLocal(av.fim)
    })
    questoes.value = av.questoes
    qtdTentativas.value = av.qtd_tentativas
  }
})

async function salvar(publicar = null) {
  salvando.value = true
  msg.value = { texto: '' }
  const corpo = {
    ...form.value,
    escola_id: +form.value.escola_id, turma_id: +form.value.turma_id, disciplina_id: +form.value.disciplina_id,
    duracao_min: form.value.duracao_min ? +form.value.duracao_min : null,
    nota_total: +form.value.nota_total, peso_objetiva: +form.value.peso_objetiva, peso_dissertativa: +form.value.peso_dissertativa,
    inicio: deInputLocal(form.value.inicio), fim: deInputLocal(form.value.fim)
  }
  if (publicar !== null) corpo.publicada = publicar
  if (corpo.publicada && !questoes.value.length) {
    salvando.value = false
    return avisar('Adicione pelo menos uma questão antes de publicar.', 'erro')
  }
  try {
    const av = props.id
      ? await api(`/api/avaliacoes/${props.id}`, { method: 'PUT', body: corpo })
      : await api('/api/avaliacoes', { method: 'POST', body: corpo })
    form.value.publicada = av.publicada
    if (av.questoes) { questoes.value = av.questoes; pesosEditados.value = {} }
    if (!props.id) {
      router.replace(`/avaliacoes/${av.id}`)
      avisar('Avaliação criada! Agora adicione as questões abaixo.')
    } else {
      avisar(av.publicada ? 'Avaliação salva e publicada para os alunos.' : 'Avaliação salva (rascunho — alunos ainda não veem).')
    }
  } catch (e) { avisar(e.message, 'erro') } finally { salvando.value = false }
}

async function salvarQuestao() {
  const q = qForm.value
  const corpo = {
    tipo: q.tipo, enunciado: q.enunciado, peso: +q.peso, explicacao: q.explicacao || null,
    gabarito_texto: q.gabarito_texto || null,
    palavras_chave: q.palavras_chave_txt.split(/\n|;/).map((s) => s.trim()).filter(Boolean),
    alternativas: q.alternativas.filter((a) => a.texto.trim())
  }
  try {
    const salva = q.id
      ? await api(`/api/questoes/${q.id}`, { method: 'PUT', body: corpo })
      : await api(`/api/avaliacoes/${props.id}/questoes`, { method: 'POST', body: corpo })
    qForm.value = null
    questoes.value = (await api(`/api/avaliacoes/${props.id}`)).questoes // valores redistribuídos
  } catch (e) { alert(e.message) }
}

async function excluirQuestao(q) {
  if (!confirm('Excluir esta questão?')) return
  try {
    await api(`/api/questoes/${q.id}`, { method: 'DELETE' })
    questoes.value = (await api(`/api/avaliacoes/${props.id}`)).questoes
  } catch (e) { alert(e.message) }
}

async function mover(i, d) {
  const j = i + d
  if (j < 0 || j >= questoes.value.length) return
  const arr = questoes.value
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
  await api(`/api/avaliacoes/${props.id}/ordem`, { method: 'PUT', body: { ids: arr.map((q) => q.id) } })
}
</script>

<template>
  <div class="cabecalho">
    <div>
      <router-link to="/painel" class="sub">← Avaliações</router-link>
      <h1>{{ id ? 'Editar avaliação' : 'Nova avaliação' }}</h1>
    </div>
    <div class="acoes" v-if="id">
      <span class="tag" :class="form.publicada ? 'ok' : 'cinza'">{{ form.publicada ? 'Publicada' : 'Rascunho' }}</span>
      <router-link class="btn sec" :to="`/avaliacoes/${id}/resultados`">Ver resultados</router-link>
    </div>
  </div>

  <div v-if="msg.texto" class="aviso" :class="msg.tipo">{{ msg.texto }}</div>

  <form class="card" @submit.prevent="salvar()">
    <h2>Dados da avaliação</h2>
    <div class="linha">
      <div class="campo" style="grid-column: span 2"><label>Título</label>
        <input v-model="form.titulo" required placeholder="Ex.: Prova Bimestral de Matemática" /></div>
      <div class="campo"><label>Tipo</label>
        <select v-model="form.tipo"><option value="prova">Prova</option><option value="simulado">Simulado</option><option value="teste">Teste</option></select></div>
    </div>
    <div class="linha">
      <div class="campo"><label>Escola</label>
        <select v-model="form.escola_id" required @change="form.turma_id = ''; form.disciplina_id = ''">
          <option value="" disabled>Selecione…</option>
          <option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option>
        </select></div>
      <div class="campo"><label>Turma</label>
        <select v-model="form.turma_id" required>
          <option value="" disabled>Selecione…</option>
          <option v-for="t in turmasDaEscola" :key="t.id" :value="t.id">{{ t.nome }} ({{ t.qtd_alunos }} alunos)</option>
        </select></div>
      <div class="campo"><label>Disciplina</label>
        <select v-model="form.disciplina_id" required>
          <option value="" disabled>Selecione…</option>
          <option v-for="d in disciplinasDaEscola" :key="d.id" :value="d.id">{{ d.nome }}</option>
        </select></div>
    </div>
    <div class="linha">
      <div class="campo"><label>Disponível a partir de</label><input type="datetime-local" v-model="form.inicio" required /></div>
      <div class="campo"><label>Encerra em</label><input type="datetime-local" v-model="form.fim" required /></div>
      <div class="campo"><label>Tempo para responder (min)</label>
        <input type="number" min="1" v-model="form.duracao_min" placeholder="Sem limite" /></div>
    </div>
    <div class="linha">
      <div class="campo"><label>Nota total da avaliação</label>
        <input type="number" step="any" min="0.1" v-model="form.nota_total" required :disabled="bloqueada" /></div>
      <div class="campo"><label>Peso padrão — objetiva</label>
        <input type="number" step="any" min="0.1" v-model="form.peso_objetiva" required /></div>
      <div class="campo"><label>Peso padrão — dissertativa</label>
        <input type="number" step="any" min="0.1" v-model="form.peso_dissertativa" required /></div>
    </div>
    <p class="sub" style="margin: -.4rem 0 .9rem; font-size: .85rem">
      A nota total é repartida entre as questões proporcionalmente ao peso de cada uma. Os pesos padrão são
      sugeridos ao criar uma questão; você pode mudar o peso de cada questão individualmente.
    </p>
    <div class="campo"><label>Instruções para o aluno (opcional)</label>
      <textarea v-model="form.descricao" rows="2"></textarea></div>
    <div class="linha">
      <div class="campo">
        <label class="check"><input type="checkbox" v-model="form.embaralhar_questoes" /> Embaralhar a ordem das questões</label>
        <label class="check"><input type="checkbox" v-model="form.embaralhar_alternativas" /> Embaralhar as alternativas</label>
        <label class="check"><input type="checkbox" v-model="form.monitorar" /> Monitorar a prova (troca de aba, saída da janela,
          fechamento do navegador) — o aluno é avisado</label>
      </div>
      <div class="campo"><label>Quando o aluno vê a correção e o feedback</label>
        <select v-model="form.liberar_resultado">
          <option value="apos_fim">Após o encerramento da avaliação (recomendado)</option>
          <option value="apos_envio">Imediatamente após enviar</option>
          <option value="manual">Quando eu liberar manualmente</option>
        </select></div>
    </div>
    <div class="acoes">
      <button :disabled="salvando">{{ id ? 'Salvar' : 'Criar e adicionar questões' }}</button>
      <template v-if="id">
        <button v-if="!form.publicada" type="button" class="sec" :disabled="salvando" @click="salvar(true)">Salvar e publicar</button>
        <button v-else type="button" class="sec" :disabled="salvando" @click="salvar(false)">Voltar para rascunho</button>
      </template>
    </div>
  </form>

  <section v-if="id" class="card">
    <div class="cabecalho" style="margin-bottom: .5rem">
      <h2 style="margin: 0">Questões ({{ questoes.length }}) · {{ fmt(totalPontos) }} pontos</h2>
      <div class="acoes" v-if="!bloqueada">
        <button class="sec" @click="novaQuestao('objetiva')">+ Objetiva</button>
        <button class="sec" @click="novaQuestao('dissertativa')">+ Dissertativa</button>
        <button @click="importando = true">📥 Importar de Word/PDF</button>
      </div>
    </div>
    <div v-if="bloqueada" class="aviso alerta">
      {{ qtdTentativas }} aluno(s) já iniciaram esta avaliação, então as questões não podem mais ser alteradas.
      Use "Duplicar" no painel para criar uma nova versão.
    </div>

    <div v-if="questoes.length" class="card distrib">
      <div class="cabecalho" style="margin-bottom: .5rem">
        <h3 style="margin: 0">Distribuição da nota ({{ fmt(form.nota_total) }} pontos)</h3>
        <div class="acoes" v-if="!bloqueada">
          <button class="sec pequeno" @click="aplicarPadrao">Aplicar pesos padrão</button>
          <button class="pequeno" :disabled="!pesosAlterados" @click="salvarPesos">Salvar pesos</button>
        </div>
      </div>
      <div class="tabela-rola">
        <table>
          <thead><tr><th>#</th><th>Tipo</th><th>Questão</th><th class="num">Peso</th><th class="num">Vale</th><th class="num">% da nota</th></tr></thead>
          <tbody>
            <tr v-for="(q, i) in questoes" :key="q.id">
              <td>{{ i + 1 }}</td>
              <td><span class="tag" :class="q.tipo === 'objetiva' ? '' : 'alerta'">{{ q.tipo === 'objetiva' ? 'Objetiva' : 'Dissertativa' }}</span></td>
              <td class="trunc">{{ q.enunciado.replace(/\[imagem:[0-9a-f]+\]/g, '🖼') }}</td>
              <td class="num"><input type="number" step="any" min="0.1" class="peso" :disabled="bloqueada"
                :value="pesoDe(q)" @input="pesosEditados[q.id] = $event.target.value" /></td>
              <td class="num"><strong>{{ fmt(valorPrevisto(q)) }}</strong></td>
              <td class="num">{{ somaPesos ? Math.round((100 * pesoDe(q)) / somaPesos) : 0 }}%</td>
            </tr>
          </tbody>
          <tfoot><tr><td colspan="3"><small class="sub">Objetivas: {{ fmt(somaPorTipo('objetiva')) }} pt ·
            Dissertativas: {{ fmt(somaPorTipo('dissertativa')) }} pt</small></td>
            <td class="num"><small>Σ {{ fmt(somaPesos) }}</small></td><td class="num"><strong>{{ fmt(form.nota_total) }}</strong></td><td></td></tr></tfoot>
        </table>
      </div>
      <div v-if="alertaPeso" class="aviso alerta" style="margin: .6rem 0 0">
        Atenção: há dissertativa com peso menor ou igual ao de uma objetiva.
      </div>
      <small v-if="pesosAlterados" class="sub">Pesos alterados — clique em "Salvar pesos" para aplicar.</small>
    </div>

    <div v-for="(q, i) in questoes" :key="q.id" class="card" style="background: var(--bg)">
      <div class="cabecalho" style="margin-bottom: .4rem">
        <div class="acoes">
          <strong>{{ i + 1 }}.</strong>
          <span class="tag" :class="q.tipo === 'objetiva' ? '' : 'alerta'">{{ q.tipo === 'objetiva' ? 'Objetiva' : 'Dissertativa' }}</span>
          <span class="sub">peso {{ fmt(q.peso) }} · vale {{ fmt(q.pontos) }} pt</span>
        </div>
        <div class="acoes" v-if="!bloqueada">
          <button class="sec pequeno" :disabled="i === 0" @click="mover(i, -1)" title="Subir">↑</button>
          <button class="sec pequeno" :disabled="i === questoes.length - 1" @click="mover(i, 1)" title="Descer">↓</button>
          <button class="sec pequeno" @click="editarQuestao(q)">Editar</button>
          <button class="perigo pequeno" @click="excluirQuestao(q)">Excluir</button>
        </div>
      </div>
      <TextoComImagens class="enunciado" :texto="q.enunciado" />
      <ol v-if="q.tipo === 'objetiva'" type="A" style="margin: 0">
        <li v-for="a in q.alternativas" :key="a.id" :style="a.correta ? 'color: var(--ok); font-weight: 600' : ''">
          <TextoComImagens tag="span" :texto="a.texto" /> <span v-if="a.correta">✓ gabarito</span>
        </li>
      </ol>
      <div v-else class="sub">
        <div v-if="q.gabarito_texto"><strong>Gabarito:</strong> <TextoComImagens tag="span" :texto="q.gabarito_texto" /></div>
        <div v-if="q.palavras_chave?.length"><strong>Palavras-chave:</strong> {{ q.palavras_chave.join(' · ') }}</div>
      </div>
    </div>
    <p v-if="!questoes.length" class="vazio">Nenhuma questão ainda. Adicione questões objetivas ou dissertativas.</p>
  </section>

  <ImportarQuestoes v-if="importando" :avaliacao-id="id" :tem-questoes="questoes.length > 0"
    :peso-objetiva="+form.peso_objetiva" :peso-dissertativa="+form.peso_dissertativa"
    @importado="aoImportar" @fechar="importando = false" />

  <!-- MODAL QUESTÃO -->
  <div v-if="qForm" class="modal-fundo">
    <form class="modal" @submit.prevent="salvarQuestao">
      <h2>{{ qForm.id ? 'Editar' : 'Nova' }} questão {{ qForm.tipo }}</h2>
      <div class="campo"><label>Enunciado <small class="sub">— use 🖼 Imagem, cole um print (Ctrl+V) ou arraste a figura</small></label>
        <EditorTexto v-model="qForm.enunciado" :rows="4" required /></div>
      <div class="acoes campo" style="align-items: end">
        <div style="max-width: 160px"><label>Peso da questão</label>
          <input type="number" step="any" min="0.1" v-model="qForm.peso" required /></div>
        <small class="sub" style="padding-bottom: .6rem">
          Valerá ≈ {{ fmt(form.nota_total * qForm.peso / (somaPesos - (qForm.id ? +pesoDe(questoes.find(x => x.id === qForm.id)) : 0) + +qForm.peso || 1)) }}
          de {{ fmt(form.nota_total) }} pontos
        </small>
      </div>

      <template v-if="qForm.tipo === 'objetiva'">
        <label>Alternativas — marque a correta (gabarito)</label>
        <div v-for="(a, i) in qForm.alternativas" :key="i" class="acoes" style="margin-bottom: .4rem; flex-wrap: nowrap">
          <input type="radio" name="correta" :checked="a.correta" @change="marcarCorreta(i)" :title="'Correta'" />
          <strong style="width: 1.2rem">{{ LETRAS[i] }}</strong>
          <EditorTexto linha v-model="a.texto" :placeholder="`Alternativa ${LETRAS[i]}`" />
          <button type="button" class="perigo pequeno" :disabled="qForm.alternativas.length <= 2"
            @click="qForm.alternativas.splice(i, 1); if (!qForm.alternativas.some(x => x.correta)) marcarCorreta(0)">✕</button>
        </div>
        <button type="button" class="btn-link" v-if="qForm.alternativas.length < 10"
          @click="qForm.alternativas.push({ texto: '', correta: false })">+ alternativa</button>
      </template>

      <template v-else>
        <div class="campo"><label>Resposta esperada (gabarito)</label>
          <EditorTexto v-model="qForm.gabarito_texto" :rows="3" placeholder="Mostrada ao aluno no feedback" /></div>
        <div class="campo"><label>Palavras-chave para correção automática (uma por linha)</label>
          <textarea v-model="qForm.palavras_chave_txt" rows="4" placeholder="fotossíntese&#10;luz|solar|luminosa&#10;gás carbônico|CO2"></textarea>
          <small class="sub">Cada linha vale uma fração igual dos pontos. Use <code>|</code> para sinônimos.
            A correção ignora acentos e maiúsculas e tolera pequenos erros de digitação.
            Você poderá revisar a nota de cada aluno depois.</small></div>
      </template>

      <div class="campo" style="margin-top: .75rem"><label>Explicação / comentário para o feedback (opcional)</label>
        <EditorTexto v-model="qForm.explicacao" :rows="2" placeholder="Por que esta é a resposta correta?" /></div>
      <div class="acoes"><button>Salvar questão</button><button type="button" class="sec" @click="qForm = null">Cancelar</button></div>
    </form>
  </div>
</template>

<style scoped>
.peso { width: 80px; text-align: right; padding: .3rem .4rem; }
.trunc { max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.distrib tfoot td { border-bottom: none; }
</style>
