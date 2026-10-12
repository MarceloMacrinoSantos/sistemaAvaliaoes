<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, sessao } from '../../api'
import ImportarAlunos from '../../components/ImportarAlunos.vue'

const msg = ref({ tipo: '', texto: '' })
const escolas = ref([])
const turmas = ref([])
const disciplinas = ref([])
const alunos = ref([])
const professores = ref([])
const ehAdmin = computed(() => sessao.usuario?.papel === 'admin')
const aba = ref('escolas')
const config = ref(null)                     // admin: cadastro de professores aberto / código de convite
const totalAlunos = computed(() => turmas.value.reduce((s, t) => s + (t.qtd_alunos || 0), 0))
const passos = computed(() => [
  { n: 1, txt: 'Cadastre sua escola', ok: escolas.value.length > 0, aba: 'escolas' },
  { n: 2, txt: 'Cadastre suas disciplinas', ok: disciplinas.value.length > 0, aba: 'disciplinas' },
  { n: 3, txt: 'Crie suas turmas', ok: turmas.value.length > 0, aba: 'turmas' },
  { n: 4, txt: 'Importe ou cadastre os alunos', ok: totalAlunos.value > 0, aba: 'alunos' }
])
const salvarConfig = () => executar(async () => {
  config.value = await api('/api/config', { method: 'PUT', body: config.value })
}, 'Configuração salva')
const perfil = ref(null)                     // /api/auth/me (vínculos do professor)
const novoVinculo = ref({})                  // professor_id -> { escola_id, disciplina_id }
const somenteProfessores = computed(() => professores.value.filter((p) => p.papel === 'professor'))
const discDaEscola = (eid) => disciplinas.value.filter((d) => !eid || d.escola_id === +eid || !d.escola_id)

const novaEscola = ref('')
const novaDisciplina = ref({ nome: '', escola_id: '' })
const novaTurma = ref({ nome: '', escola_id: '', ano_letivo: String(new Date().getFullYear()), professor_id: '' })
const turmaAlunos = ref('')
const novoAluno = ref({ nome: '', login: '', senha: '' })
const mostrarImport = ref(false)
const novoProf = ref({ nome: '', login: '', senha: '', papel: 'professor' })
const editando = ref(null) // {tipo, id, ...campos}

function avisar(texto, tipo = 'ok') {
  msg.value = { texto, tipo }
  setTimeout(() => { if (msg.value.texto === texto) msg.value = { texto: '', tipo: '' } }, 5000)
}

async function executar(fn, sucesso) {
  try {
    await fn()
    if (sucesso) avisar(sucesso)
  } catch (e) { avisar(e.message, 'erro') }
}

async function carregarBase() {
  ;[escolas.value, turmas.value, disciplinas.value] = await Promise.all([
    api('/api/escolas'), api('/api/turmas'), api('/api/disciplinas')])
  if (ehAdmin.value) {
    config.value = await api('/api/config')
    professores.value = await api('/api/professores')
    for (const p of professores.value) novoVinculo.value[p.id] ||= { escola_id: '', disciplina_id: '' }
  }
  else perfil.value = await api('/api/auth/me')
  if (escolas.value.length === 1) {
    novaTurma.value.escola_id ||= escolas.value[0].id
    novaDisciplina.value.escola_id ||= escolas.value[0].id
  }
}
const selecionados = ref(new Set())
const lotes = ref([])
const excluirTodos = ref(null)   // { confirmacao }
const turmaAtual = computed(() => turmas.value.find((t) => t.id === +turmaAlunos.value))
const todosMarcados = computed(() => alunos.value.length && alunos.value.every((a) => selecionados.value.has(a.id)))
function alternarTodos() {
  selecionados.value = todosMarcados.value ? new Set() : new Set(alunos.value.map((a) => a.id))
}
function alternar(id) {
  const s = new Set(selecionados.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selecionados.value = s
}
async function excluirLote(modo, extra = {}) {
  const r = await api('/api/alunos/excluir-lote', { method: 'POST', body: { turma_id: +turmaAlunos.value, modo, ...extra } })
  selecionados.value = new Set()
  excluirTodos.value = null
  await Promise.all([carregarAlunos(), carregarBase()])
  avisar(`${r.excluidos} aluno(s) excluído(s)` + (r.tentativas_apagadas ? ` e ${r.tentativas_apagadas} prova(s) respondida(s) apagada(s)` : ''))
}
const excluirSelecionados = () => {
  if (!confirm(`Excluir ${selecionados.value.size} aluno(s) selecionado(s)? As provas que eles já fizeram também serão apagadas.`)) return
  executar(() => excluirLote('selecionados', { ids: [...selecionados.value] }))
}
const desfazerLote = (l) => {
  if (!confirm(`Desfazer a importação "${l.lote}"? ${l.qtd} aluno(s) dessa importação sairão da turma.`)) return
  executar(() => excluirLote('lote', { lote: l.lote }))
}
const confirmarExcluirTodos = () => executar(() => excluirLote('todos', { confirmacao: excluirTodos.value.confirmacao }))
function aoImportar(r) {
  carregarAlunos(); carregarBase()
  if (!r.erros.length) {
    mostrarImport.value = false
    avisar(`${r.criados} aluno(s) importado(s)` + (r.matriculados ? `, ${r.matriculados} já cadastrado(s) e matriculado(s) nesta turma` : '') +
      (r.atualizados ? `, ${r.atualizados} atualizado(s)` : ''))
  }
}

async function carregarAlunos() {
  selecionados.value = new Set()
  alunos.value = turmaAlunos.value ? await api(`/api/alunos?turma_id=${turmaAlunos.value}`) : []
  lotes.value = turmaAlunos.value ? await api(`/api/alunos/lotes?turma_id=${turmaAlunos.value}`) : []
}
onMounted(() => executar(async () => {
  await carregarBase()
  if (!ehAdmin.value) aba.value = passos.value.find((p) => !p.ok)?.aba || 'turmas'
}))
watch(turmaAlunos, () => executar(carregarAlunos))

const criarEscola = () => executar(async () => {
  await api('/api/escolas', { method: 'POST', body: { nome: novaEscola.value } })
  novaEscola.value = ''
  await carregarBase()
}, 'Escola cadastrada')

const criarDisciplina = () => executar(async () => {
  await api('/api/disciplinas', { method: 'POST', body: { nome: novaDisciplina.value.nome, escola_id: +novaDisciplina.value.escola_id || null } })
  novaDisciplina.value.nome = ''
  await carregarBase()
}, 'Disciplina cadastrada')

const criarTurma = () => executar(async () => {
  await api('/api/turmas', { method: 'POST', body: { ...novaTurma.value, escola_id: +novaTurma.value.escola_id,
    professor_id: +novaTurma.value.professor_id || null } })
  novaTurma.value.nome = ''
  await carregarBase()
}, 'Turma cadastrada')

const criarAluno = () => executar(async () => {
  const r = await api('/api/alunos', { method: 'POST', body: { ...novoAluno.value, turma_id: +turmaAlunos.value, senha: novoAluno.value.senha || null } })
  novoAluno.value = { nome: '', login: '', senha: '' }
  await Promise.all([carregarAlunos(), carregarBase()])
  avisar(r.ja_existia ? `${r.nome} já tinha cadastro (RM ${r.login}) e foi matriculado(a) nesta turma — a senha dele(a) não mudou.` : 'Aluno cadastrado')
})

const adicionarVinculo = (p) => executar(async () => {
  const v = novoVinculo.value[p.id] || {}
  await api(`/api/professores/${p.id}/vinculos`, { method: 'POST', body: { escola_id: +v.escola_id, disciplina_id: +v.disciplina_id } })
  novoVinculo.value[p.id] = { escola_id: v.escola_id, disciplina_id: '' }
  await carregarBase()
}, 'Vínculo adicionado')
const mudarPerfil = (p) => {
  const novo = p.papel === 'admin' ? 'professor' : 'admin'
  const txt = novo === 'admin' ? `${p.nome} passará a ver e cadastrar TUDO (todas as escolas, professores e alunos).`
    : `${p.nome} passará a ver só as escolas/disciplinas dos vínculos dele.`
  if (!confirm(`${txt} Continuar?`)) return
  executar(async () => { await api(`/api/professores/${p.id}`, { method: 'PUT', body: { papel: novo } }); await carregarBase() },
    'Perfil alterado. A pessoa precisa sair e entrar de novo.')
}
const redefinirSenha = (p) => {
  const senha = prompt(`Nova senha para ${p.nome} (mínimo 4 caracteres):`)
  if (!senha) return
  executar(() => api(`/api/professores/${p.id}`, { method: 'PUT', body: { senha } }), 'Senha redefinida')
}
const removerVinculo = (p, v) => {
  if (!confirm(`Remover o vínculo de ${p.nome} com ${v.disciplina} (${v.escola})? As turmas e avaliações dele não são apagadas.`)) return
  executar(async () => { await api(`/api/vinculos/${v.id}`, { method: 'DELETE' }); await carregarBase() }, 'Vínculo removido')
}

const criarProf = () => executar(async () => {
  await api('/api/professores', { method: 'POST', body: novoProf.value })
  novoProf.value = { nome: '', login: '', senha: '', papel: 'professor' }
  await carregarBase()
}, 'Usuário cadastrado')

function excluir(tipo, item) {
  const nomes = { escolas: 'a escola', turmas: 'a turma', disciplinas: 'a disciplina', alunos: 'o aluno', professores: 'o usuário' }
  const extra = tipo === 'alunos' ? ' da turma (as provas dele nesta turma também serão apagadas)' : ''
  if (!confirm(`Excluir ${nomes[tipo]} "${item.nome}"${extra}?`)) return
  executar(async () => {
    await api(`/api/${tipo}/${item.id}` + (tipo === 'alunos' ? `?turma_id=${turmaAlunos.value}` : ''), { method: 'DELETE' })
    await carregarBase()
    if (tipo === 'alunos') await carregarAlunos()
  }, 'Excluído')
}

function editar(tipo, item) {
  editando.value = { tipo, ...item, senha: '', turma_atual_id: item.turma_id, professor_id: item.professor_id || '', escola_id: item.escola_id || '' }
}
const salvarEdicao = () => executar(async () => {
  const e = editando.value
  const corpo = {
    escolas: { nome: e.nome },
    disciplinas: { nome: e.nome, escola_id: +e.escola_id || null },
    turmas: { nome: e.nome, escola_id: +e.escola_id, ano_letivo: e.ano_letivo, professor_id: +e.professor_id || null },
    alunos: { nome: e.nome, login: e.login, turma_id: +e.turma_id, turma_atual_id: e.turma_atual_id, senha: e.senha || null }
  }[e.tipo]
  await api(`/api/${e.tipo}/${e.id}`, { method: 'PUT', body: corpo })
  editando.value = null
  await carregarBase()
  await carregarAlunos()
}, 'Alterações salvas')
</script>

<template>
  <div class="cabecalho">
    <div>
      <h1>Cadastros</h1>
      <p class="sub">{{ ehAdmin ? 'Escolas, disciplinas, turmas, alunos e professores.' : 'Sua área: só você vê o que cadastrar aqui.' }}</p>
    </div>
  </div>

  <div v-if="!ehAdmin && passos.some((p) => !p.ok)" class="card passos">
    <strong>Primeiros passos</strong>
    <div class="lista-passos">
      <button v-for="p in passos" :key="p.n" class="passo" :class="{ feito: p.ok }" @click="aba = p.aba">
        <span class="bola">{{ p.ok ? '✓' : p.n }}</span> {{ p.txt }}</button>
      <router-link class="passo" to="/avaliacoes/nova"><span class="bola">5</span> Crie a avaliação</router-link>
    </div>
  </div>
  <div v-if="!ehAdmin && perfil?.vinculos?.length" class="card vinc">
    <strong>Liberado pelo administrador:</strong>
    <span v-for="(v, i) in perfil.vinculos" :key="i" class="tag">{{ v.escola }} · {{ v.disciplina }}</span>
  </div>

  <div v-if="msg.texto" class="aviso" :class="msg.tipo">{{ msg.texto }}</div>

  <div class="abas">
    <button :class="{ ativa: aba === 'escolas' }" @click="aba = 'escolas'">{{ ehAdmin ? 'Escolas' : 'Minhas escolas' }} ({{ escolas.length }})</button>
    <button :class="{ ativa: aba === 'disciplinas' }" @click="aba = 'disciplinas'">{{ ehAdmin ? 'Disciplinas' : 'Minhas disciplinas' }} ({{ disciplinas.length }})</button>
    <button :class="{ ativa: aba === 'turmas' }" @click="aba = 'turmas'">{{ ehAdmin ? 'Turmas' : 'Minhas turmas' }} ({{ turmas.length }})</button>
    <button :class="{ ativa: aba === 'alunos' }" @click="aba = 'alunos'">Alunos</button>
    <button v-if="ehAdmin" :class="{ ativa: aba === 'professores' }" @click="aba = 'professores'">Professores</button>
  </div>

  <!-- ESCOLAS -->
  <section v-if="aba === 'escolas'" class="card">
    <form class="acoes" @submit.prevent="criarEscola" style="margin-bottom: 1rem">
      <input v-model="novaEscola" placeholder="Nome da escola" required style="flex: 1; min-width: 200px" />
      <button>Adicionar</button>
    </form>
    <table v-if="escolas.length">
      <tbody>
        <tr v-for="e in escolas" :key="e.id">
          <td>{{ e.nome }}<br v-if="ehAdmin || !e.editavel" /><small class="sub" v-if="ehAdmin">{{ e.criado_por ? `área de ${e.criado_por}` : 'cadastrada pelo administrador' }}</small>
            <small class="sub" v-else-if="!e.editavel">liberada pelo administrador</small></td>
          <td class="num"><div v-if="e.editavel" class="acoes" style="justify-content: flex-end">
            <button class="sec pequeno" @click="editar('escolas', e)">Editar</button>
            <button class="perigo pequeno" @click="excluir('escolas', e)">Excluir</button>
          </div></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="vazio">Nenhuma escola cadastrada.</p>
  </section>

  <!-- TURMAS -->
  <section v-if="aba === 'turmas'" class="card">
    <form class="linha" @submit.prevent="criarTurma" style="margin-bottom: 1rem; align-items: end">
      <div><label>Escola</label>
        <select v-model="novaTurma.escola_id" required>
          <option value="" disabled>Selecione…</option>
          <option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option>
        </select></div>
      <div><label>Nome da turma</label><input v-model="novaTurma.nome" placeholder="Ex.: 9º Ano A" required /></div>
      <div><label>Ano letivo</label><input v-model="novaTurma.ano_letivo" /></div>
      <div v-if="ehAdmin"><label>Professor responsável</label>
        <select v-model="novaTurma.professor_id">
          <option value="">— nenhum (só admin) —</option>
          <option v-for="p in somenteProfessores" :key="p.id" :value="p.id">{{ p.nome }}</option>
        </select></div>
      <div><button style="width: 100%; justify-content: center" :disabled="!escolas.length">Adicionar</button></div>
    </form>
    <table v-if="turmas.length">
      <thead><tr><th>Turma</th><th>Escola</th><th>Ano</th><th v-if="ehAdmin">Professor</th><th class="num">Alunos</th><th></th></tr></thead>
      <tbody>
        <tr v-for="t in turmas" :key="t.id">
          <td>{{ t.nome }}</td><td>{{ t.escola }}</td><td>{{ t.ano_letivo }}</td>
          <td v-if="ehAdmin">{{ t.professor || '—' }}</td><td class="num">{{ t.qtd_alunos }}</td>
          <td class="num"><div class="acoes" style="justify-content: flex-end">
            <button class="sec pequeno" @click="aba = 'alunos'; turmaAlunos = t.id">Alunos</button>
            <button class="sec pequeno" @click="editar('turmas', t)">Editar</button>
            <button class="perigo pequeno" @click="excluir('turmas', t)">Excluir</button>
          </div></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="vazio">Nenhuma turma cadastrada.</p>
  </section>

  <!-- DISCIPLINAS -->
  <section v-if="aba === 'disciplinas'" class="card">
    <form class="linha" @submit.prevent="criarDisciplina" style="margin-bottom: 1rem; align-items: end">
      <div><label>Escola</label>
        <select v-model="novaDisciplina.escola_id" required>
          <option value="" disabled>Selecione…</option>
          <option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option>
        </select></div>
      <div><label>Nome da disciplina</label><input v-model="novaDisciplina.nome" required /></div>
      <div><button style="width: 100%; justify-content: center">Adicionar</button></div>
    </form>
    <table v-if="disciplinas.length">
      <thead><tr><th>Disciplina</th><th>Escola</th><th></th></tr></thead>
      <tbody>
        <tr v-for="d in disciplinas" :key="d.id">
          <td>{{ d.nome }}<br v-if="!d.editavel" /><small v-if="!d.editavel" class="sub">liberada pelo administrador</small></td>
          <td>{{ d.escola || '— sem escola —' }}</td>
          <td class="num"><div v-if="d.editavel" class="acoes" style="justify-content: flex-end">
            <button class="sec pequeno" @click="editar('disciplinas', d)">Editar</button>
            <button class="perigo pequeno" @click="excluir('disciplinas', d)">Excluir</button>
          </div></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="vazio">Nenhuma disciplina cadastrada.</p>
  </section>

  <!-- ALUNOS -->
  <section v-if="aba === 'alunos'" class="card">
    <div class="campo" style="max-width: 420px">
      <label>Turma</label>
      <select v-model="turmaAlunos">
        <option value="">Selecione a turma…</option>
        <option v-for="t in turmas" :key="t.id" :value="t.id">{{ t.nome }} — {{ t.escola }}</option>
      </select>
    </div>
    <template v-if="turmaAlunos">
      <form class="linha" @submit.prevent="criarAluno" style="align-items: end">
        <div><label>Nome do aluno</label><input v-model="novoAluno.nome" required /></div>
        <div><label>Matrícula / login</label><input v-model="novoAluno.login" required autocapitalize="off" /></div>
        <div><label>Senha (padrão: a matrícula)</label><input v-model="novoAluno.senha" /></div>
        <div><button style="width: 100%; justify-content: center">Adicionar</button></div>
      </form>
      <div class="acoes" style="margin: .8rem 0">
        <button class="sec" @click="mostrarImport = !mostrarImport">📥 Importar de planilha / CSV / JSON</button>
      </div>
      <ImportarAlunos v-if="mostrarImport" :turma-id="turmaAlunos" :turma-nome="turmaAtual?.nome"
        @importado="aoImportar" @fechar="mostrarImport = false" />

      <div v-if="alunos.length" class="acoes barra-acoes">
        <strong>{{ alunos.length }} aluno(s)</strong>
        <button class="perigo pequeno" :disabled="!selecionados.size" @click="excluirSelecionados">
          Excluir selecionados ({{ selecionados.size }})</button>
        <button class="perigo pequeno" @click="excluirTodos = { confirmacao: '' }">Excluir todos da turma</button>
        <details v-if="lotes.length" class="lotes">
          <summary class="btn sec pequeno">↶ Desfazer importação</summary>
          <div class="lotes-lista">
            <div v-for="l in lotes" :key="l.lote" class="acoes" style="justify-content: space-between">
              <small>{{ l.lote }} — <b>{{ l.qtd }}</b> aluno(s)</small>
              <button class="perigo pequeno" @click="desfazerLote(l)">Desfazer</button>
            </div>
          </div>
        </details>
      </div>
      <div class="tabela-rola">
        <table v-if="alunos.length">
          <thead><tr><th style="width: 2rem"><input type="checkbox" :checked="todosMarcados" @change="alternarTodos" title="Marcar todos" /></th>
            <th>Nome</th><th>RM / login</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in alunos" :key="a.id" :class="{ sel: selecionados.has(a.id) }">
              <td><input type="checkbox" :checked="selecionados.has(a.id)" @change="alternar(a.id)" /></td>
              <td>{{ a.nome }}</td><td><code>{{ a.login }}</code></td>
              <td class="num"><div class="acoes" style="justify-content: flex-end">
                <button class="sec pequeno" @click="editar('alunos', a)">Editar / senha</button>
                <button class="perigo pequeno" @click="excluir('alunos', a)">Excluir</button>
              </div></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="vazio">Nenhum aluno nesta turma.</p>
      </div>
    </template>
  </section>

  <!-- PROFESSORES -->
  <section v-if="aba === 'professores' && ehAdmin" class="card">
    <form class="linha" @submit.prevent="criarProf" style="margin-bottom: 1rem; align-items: end">
      <div><label>Nome</label><input v-model="novoProf.nome" required /></div>
      <div><label>Login</label><input v-model="novoProf.login" required autocapitalize="off" /></div>
      <div><label>Senha</label><input v-model="novoProf.senha" required /></div>
      <div><label>Perfil</label>
        <select v-model="novoProf.papel"><option value="professor">Professor</option><option value="admin">Administrador</option></select></div>
      <div><button style="width: 100%; justify-content: center">Adicionar</button></div>
    </form>
    <div v-if="config" class="card" style="background: var(--bg)">
      <strong>Cadastro de professores pela tela de login</strong>
      <div class="linha" style="align-items: end; margin-top: .5rem">
        <label class="check"><input type="checkbox" v-model="config.cadastro_aberto" /> Permitir que professores criem a própria conta</label>
        <div><label>Código de convite (opcional)</label><input v-model="config.codigo_convite" placeholder="vazio = qualquer pessoa" /></div>
        <div><button class="pequeno" @click="salvarConfig">Salvar</button></div>
      </div>
      <small class="sub">Com código, só quem o tiver consegue se cadastrar. Recomendado se o sistema estiver na internet.</small>
    </div>
    <p class="sub">Cada professor tem uma área particular: vê só as escolas, disciplinas, turmas e alunos que cadastrou, mais o
      que você liberar aqui com vínculos. O administrador vê tudo.</p>
    <div v-for="p in professores" :key="p.id" class="card prof">
      <div class="cabecalho" style="margin-bottom: .4rem">
        <div><strong>{{ p.nome }}</strong> <code>{{ p.login }}</code>
          <span class="tag" :class="p.papel === 'admin' ? '' : 'cinza'">{{ p.papel === 'admin' ? 'Administrador' : 'Professor' }}</span>
          <small class="sub"> · {{ p.qtd_turmas }} turma(s)</small></div>
        <div v-if="p.id !== sessao.usuario.id" class="acoes">
          <button class="sec pequeno" @click="mudarPerfil(p)">{{ p.papel === 'admin' ? 'Tornar professor' : 'Tornar administrador' }}</button>
          <button class="sec pequeno" @click="redefinirSenha(p)">Redefinir senha</button>
          <button class="perigo pequeno" @click="excluir('professores', p)">Remover</button>
        </div>
      </div>
      <template v-if="p.papel === 'professor'">
        <div class="acoes" style="margin-bottom: .5rem">
          <span v-for="v in p.vinculos" :key="v.id" class="tag vinculo">{{ v.escola }} · {{ v.disciplina }}
            <button class="btn-link" title="Remover vínculo" @click="removerVinculo(p, v)">✕</button></span>
          <span v-if="!p.vinculos.length" class="tag alerta">sem vínculo — não vê nada</span>
        </div>
        <form class="acoes" @submit.prevent="adicionarVinculo(p)">
          <select v-model="novoVinculo[p.id].escola_id" required style="width: auto">
            <option value="" disabled>Escola…</option>
            <option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option>
          </select>
          <select v-model="novoVinculo[p.id].disciplina_id" required style="width: auto" :disabled="!novoVinculo[p.id].escola_id">
            <option value="" disabled>Disciplina…</option>
            <option v-for="d in discDaEscola(novoVinculo[p.id].escola_id)" :key="d.id" :value="d.id">{{ d.nome }}</option>
          </select>
          <button class="sec pequeno">+ Vincular</button>
        </form>
      </template>
    </div>
  </section>

  <!-- EXCLUIR TODOS -->
  <div v-if="excluirTodos" class="modal-fundo" @click.self="excluirTodos = null">
    <form class="modal" style="max-width: 460px" @submit.prevent="confirmarExcluirTodos">
      <h2>Excluir todos os alunos de {{ turmaAtual?.nome }}?</h2>
      <p>Serão excluídos <b>{{ alunos.length }} aluno(s)</b> e todas as provas que eles já responderam nesta turma.
        <b>Não é possível desfazer.</b></p>
      <div class="campo"><label>Para confirmar, digite o nome da turma: <b>{{ turmaAtual?.nome }}</b></label>
        <input v-model="excluirTodos.confirmacao" autofocus /></div>
      <div class="acoes">
        <button class="perigo" :disabled="excluirTodos.confirmacao.trim().toLowerCase() !== (turmaAtual?.nome || '').trim().toLowerCase()">
          Excluir todos</button>
        <button type="button" class="sec" @click="excluirTodos = null">Cancelar</button>
      </div>
    </form>
  </div>

  <!-- MODAL DE EDIÇÃO -->
  <div v-if="editando" class="modal-fundo" @click.self="editando = null">
    <form class="modal" style="max-width: 480px" @submit.prevent="salvarEdicao">
      <h2>Editar</h2>
      <div class="campo"><label>Nome</label><input v-model="editando.nome" required /></div>
      <template v-if="editando.tipo === 'turmas'">
        <div class="campo"><label>Escola</label>
          <select v-model="editando.escola_id"><option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option></select></div>
        <div class="campo"><label>Ano letivo</label><input v-model="editando.ano_letivo" /></div>
        <div v-if="ehAdmin" class="campo"><label>Professor responsável</label>
          <select v-model="editando.professor_id"><option value="">— nenhum —</option>
            <option v-for="p in somenteProfessores" :key="p.id" :value="p.id">{{ p.nome }}</option></select></div>
      </template>
      <template v-if="editando.tipo === 'disciplinas'">
        <div class="campo"><label>Escola</label>
          <select v-model="editando.escola_id"><option value="">— sem escola —</option>
            <option v-for="e in escolas" :key="e.id" :value="e.id">{{ e.nome }}</option></select></div>
      </template>
      <template v-if="editando.tipo === 'alunos'">
        <div class="campo"><label>Login</label><input v-model="editando.login" required /></div>
        <div class="campo"><label>Turma</label>
          <select v-model="editando.turma_id"><option v-for="t in turmas" :key="t.id" :value="t.id">{{ t.nome }} — {{ t.escola }}</option></select></div>
        <div class="campo"><label>Nova senha (deixe vazio para manter)</label><input v-model="editando.senha" /></div>
      </template>
      <div class="acoes"><button>Salvar</button><button type="button" class="sec" @click="editando = null">Cancelar</button></div>
    </form>
  </div>
</template>

<style scoped>
.passos { background: var(--pri-claro); border-color: #c9d7f7; }
.lista-passos { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: .5rem; }
a.passo { display: inline-flex; align-items: center; gap: .35rem; padding: .55rem 1rem; border-radius: 8px; text-decoration: none; }
.passo { background: #fff; color: var(--texto); border: 1px solid var(--borda); font-weight: 500; }
.passo:hover { background: #fff; border-color: var(--pri); }
.passo.feito { color: var(--ok); border-color: #bfe3cf; background: var(--ok-claro); }
.bola { display: inline-flex; width: 1.4rem; height: 1.4rem; border-radius: 99px; align-items: center; justify-content: center;
  background: var(--pri); color: #fff; font-size: .8rem; }
.passo.feito .bola { background: var(--ok); }
.vinc { display: flex; gap: .4rem; flex-wrap: wrap; align-items: center; }
.prof { background: var(--bg); margin-bottom: .6rem; }
.tag.vinculo { display: inline-flex; gap: .3rem; align-items: center; }
.barra-acoes { margin-bottom: .5rem; padding: .5rem .6rem; background: var(--bg); border-radius: 8px; }
tr.sel td { background: var(--pri-claro); }
.lotes { position: relative; }
.lotes summary { list-style: none; cursor: pointer; }
.lotes summary::-webkit-details-marker { display: none; }
.lotes-lista { position: absolute; z-index: 20; background: #fff; border: 1px solid var(--borda); border-radius: 8px;
  padding: .6rem; margin-top: .3rem; min-width: 380px; box-shadow: 0 6px 20px rgba(0,0,0,.12); display: grid; gap: .4rem; }
@media (max-width: 600px) { .lotes-lista { min-width: 0; width: 88vw; } }
</style>
