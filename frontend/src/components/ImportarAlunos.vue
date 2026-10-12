<script setup>
import { computed, ref } from 'vue'
import { api, enviarArquivo } from '../api'

// Importa alunos de planilha (.xlsx/.xls), .csv, .txt, .json ou texto colado.
// O sistema sugere quais colunas são RM, Nome e Senha; o professor confere antes de gravar.
const props = defineProps({ turmaId: [Number, String], turmaNome: String })
const emit = defineEmits(['importado', 'fechar'])

const arquivo = ref(null)
const texto = ref('')
const lendo = ref(false)
const erro = ref('')
const tabela = ref(null)        // { arquivo, linhas, largura }
const mapa = ref({})            // indice coluna -> 'rm' | 'nome' | 'senha' | ''
const temCabecalho = ref(true)
const senhaPadrao = ref('')
const atualizar = ref(false)
const importando = ref(false)
const resultado = ref(null)

function escolher(e) { arquivo.value = e.target.files[0] || null; ler() }

async function ler() {
  erro.value = ''; resultado.value = null
  lendo.value = true
  try {
    const r = await enviarArquivo('/api/alunos/ler-arquivo', arquivo.value ? { arquivo: arquivo.value } : { texto: texto.value })
    tabela.value = r
    temCabecalho.value = r.sugestao.tem_cabecalho
    const m = {}
    for (const campo of ['rm', 'nome', 'senha']) if (r.sugestao[campo] != null) m[r.sugestao[campo]] = campo
    mapa.value = m
  } catch (e) { erro.value = e.message; tabela.value = null } finally { lendo.value = false }
}

function definir(col, campo) {
  const m = { ...mapa.value }
  for (const k of Object.keys(m)) if (m[k] === campo && campo) delete m[k] // cada campo em uma coluna só
  if (campo) m[col] = campo; else delete m[col]
  mapa.value = m
}
const colDe = (campo) => { const e = Object.entries(mapa.value).find(([, v]) => v === campo); return e ? +e[0] : null }
const cabecalho = computed(() => (temCabecalho.value && tabela.value ? tabela.value.linhas[0] : null))
const dados = computed(() => (tabela.value ? tabela.value.linhas.slice(temCabecalho.value ? 1 : 0) : []))
const registros = computed(() => {
  const rm = colDe('rm'), nome = colDe('nome'), senha = colDe('senha')
  if (rm == null || nome == null) return []
  return dados.value.map((l) => ({ rm: (l[rm] || '').trim(), nome: (l[nome] || '').trim(), senha: senha != null ? (l[senha] || '').trim() : '' }))
    .filter((r) => r.rm || r.nome)
})
const invalidos = computed(() => registros.value.filter((r) => !r.rm || !r.nome).length)
const LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
const ROTULO = { rm: 'RM', nome: 'Nome', senha: 'Senha' }

async function importar() {
  importando.value = true; erro.value = ''
  try {
    resultado.value = await api('/api/alunos/importar-lista', { method: 'POST', body: {
      turma_id: +props.turmaId, alunos: registros.value.filter((r) => r.rm && r.nome),
      senha_padrao: senhaPadrao.value || null, atualizar_existentes: atualizar.value,
      origem: tabela.value.arquivo === 'colado.txt' ? 'texto colado' : tabela.value.arquivo
    } })
    emit('importado', resultado.value)
    if (!resultado.value.erros.length) tabela.value = null
  } catch (e) { erro.value = e.message } finally { importando.value = false }
}
</script>

<template>
  <div class="card imp">
    <div class="cabecalho" style="margin-bottom: .5rem">
      <h3 style="margin: 0">Importar alunos para {{ turmaNome }}</h3>
      <button class="btn-link" @click="emit('fechar')">fechar ✕</button>
    </div>
    <p class="sub">Aceita planilha do Excel (<b>.xlsx</b>, <b>.xls</b>), <b>.csv</b>, <b>.txt</b> ou <b>.json</b>, com as colunas em qualquer
      ordem e com ou sem cabeçalho. Só é preciso ter <b>RM</b> e <b>nome</b>; a <b>senha</b> é opcional.
      Modelos: <a href="/api/modelos/modelo-alunos.xlsx">Excel</a> · <a href="/api/modelos/modelo-alunos.csv">CSV</a> ·
      <a href="/api/modelos/modelo-alunos.json">JSON</a></p>

    <div class="linha" style="align-items: start">
      <div class="campo">
        <label>Arquivo</label>
        <input type="file" accept=".xlsx,.xlsm,.xls,.csv,.txt,.tsv,.json" @change="escolher" />
      </div>
      <div class="campo">
        <label>…ou cole aqui (copiado da planilha)</label>
        <textarea v-model="texto" rows="3" placeholder="2026001	Maria da Silva	senha123" @input="arquivo = null"></textarea>
        <button class="sec pequeno" style="margin-top: .3rem" :disabled="!texto.trim() || lendo" @click="ler">Ler texto colado</button>
      </div>
    </div>
    <p v-if="lendo" class="sub">Lendo…</p>
    <div v-if="erro" class="aviso erro">{{ erro }}</div>

    <template v-if="tabela">
      <div class="aviso info" style="margin-bottom: .6rem">
        Confira as colunas: escolha abaixo de cada coluna se ela é <b>RM</b>, <b>Nome</b> ou <b>Senha</b>.
        <span v-if="colDe('rm') == null || colDe('nome') == null"><br /><b>Falta indicar a coluna de {{ colDe('rm') == null ? 'RM' : 'Nome' }}.</b></span>
      </div>
      <div class="acoes" style="margin-bottom: .5rem">
        <label class="check"><input type="checkbox" v-model="temCabecalho" /> A primeira linha é cabeçalho</label>
      </div>
      <div class="tabela-rola previa">
        <table>
          <thead>
            <tr>
              <th v-for="c in tabela.largura" :key="c">
                <select :value="mapa[c - 1] || ''" @change="definir(c - 1, $event.target.value)" :class="{ marcado: mapa[c - 1] }">
                  <option value="">— ignorar —</option>
                  <option value="rm">RM</option><option value="nome">Nome</option><option value="senha">Senha</option>
                </select>
                <div class="sub" style="font-weight: 400; text-transform: none">{{ cabecalho ? cabecalho[c - 1] : `Coluna ${LETRAS[c - 1] || c}` }}</div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(l, i) in dados.slice(0, 8)" :key="i">
              <td v-for="(v, j) in l" :key="j" :class="{ usado: mapa[j] }">{{ v }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <small class="sub">Mostrando {{ Math.min(8, dados.length) }} de {{ dados.length }} linhas.</small>

      <div class="linha" style="margin-top: .8rem; align-items: end">
        <div class="campo"><label>Senha para quem estiver sem senha</label>
          <input v-model="senhaPadrao" placeholder="vazio = a própria RM" /></div>
        <div class="campo"><label class="check"><input type="checkbox" v-model="atualizar" />
          Se a RM já existir, atualizar nome e senha (o aluno é matriculado nesta turma de qualquer forma)</label></div>
      </div>
      <div class="acoes">
        <button :disabled="!registros.length || importando" @click="importar">
          {{ importando ? 'Importando…' : `Importar ${registros.length - invalidos} aluno(s)` }}</button>
        <small v-if="invalidos" class="sub">{{ invalidos }} linha(s) sem RM ou nome serão ignoradas.</small>
      </div>
    </template>

    <div v-if="resultado" class="aviso" :class="resultado.erros.length ? 'alerta' : 'ok'" style="margin-top: .8rem">
      <b>{{ resultado.criados }}</b> aluno(s) criado(s)<span v-if="resultado.matriculados">,
      <b>{{ resultado.matriculados }}</b> já tinham cadastro (em outra turma) e foram matriculados nesta</span><span v-if="resultado.atualizados">, <b>{{ resultado.atualizados }}</b> atualizado(s)</span>.
      <span v-if="resultado.lote"> Se algo saiu errado, use "Desfazer importação" na lista de alunos.</span>
      <ul v-if="resultado.erros.length" style="margin: .4rem 0 0; padding-left: 1.2rem; max-height: 160px; overflow: auto">
        <li v-for="(e, i) in resultado.erros" :key="i">{{ e }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.imp { background: var(--bg); }
.previa th { vertical-align: top; min-width: 130px; }
.previa select { padding: .3rem; font-size: .85rem; }
.previa select.marcado { border-color: var(--pri); background: var(--pri-claro); font-weight: 600; }
.previa td.usado { background: #fff; font-weight: 500; }
.previa td { color: var(--suave); white-space: nowrap; }
</style>
