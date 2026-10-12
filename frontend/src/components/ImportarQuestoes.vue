<script setup>
import { computed, ref } from 'vue'
import EditorTexto from './EditorTexto.vue'
import TextoComImagens from './TextoComImagens.vue'
import { api, enviarArquivo } from '../api'

// Importa questões de .docx, .pdf, .txt ou texto colado. Mostra uma prévia editável antes de gravar.
const props = defineProps({ avaliacaoId: [Number, String], temQuestoes: Boolean, pesoObjetiva: Number, pesoDissertativa: Number })
const emit = defineEmits(['importado', 'fechar'])

const LETRAS = 'ABCDEFGHIJ'
const arquivo = ref(null)
const texto = ref('')
const lendo = ref(false)
const erro = ref('')
const previa = ref(null)
const substituir = ref(false)
const gravando = ref(false)

async function ler(e) {
  if (e?.target?.files) arquivo.value = e.target.files[0] || null
  erro.value = ''; lendo.value = true
  try {
    const r = await enviarArquivo('/api/avaliacoes/importar/ler', arquivo.value ? { arquivo: arquivo.value } : { texto: texto.value })
    r.questoes.forEach((q) => {
      q.incluir = true
      q.palavras_txt = (q.palavras_chave || []).join('\n')
      q.peso = q.peso || (q.tipo === 'dissertativa' ? props.pesoDissertativa : props.pesoObjetiva)
    })
    previa.value = r
  } catch (e) { erro.value = e.message; previa.value = null } finally { lendo.value = false }
}

const incluidas = computed(() => previa.value?.questoes.filter((q) => q.incluir) || [])
const semGabarito = (q) => q.tipo === 'objetiva' && !q.alternativas.some((a) => a.correta)
const pendentes = computed(() => incluidas.value.filter(semGabarito).length)
function marcar(q, i) { q.alternativas.forEach((a, j) => (a.correta = i === j)) }
function mudarTipo(q) {
  if (q.tipo === 'objetiva' && q.alternativas.length < 2) q.alternativas = [0, 1, 2, 3].map(() => ({ texto: '', correta: false }))
}

async function gravar() {
  if (pendentes.value) return (erro.value = `Marque a alternativa correta em ${pendentes.value} questão(ões) destacada(s).`)
  if (substituir.value && !confirm('Substituir TODAS as questões atuais da avaliação pelas importadas?')) return
  gravando.value = true; erro.value = ''
  try {
    const questoes = incluidas.value.map((q) => ({
      tipo: q.tipo, enunciado: q.enunciado, peso: +q.peso || null, explicacao: q.explicacao || null,
      gabarito_texto: q.tipo === 'dissertativa' ? (q.gabarito_texto || null) : null,
      palavras_chave: q.tipo === 'dissertativa' ? q.palavras_txt.split(/\n|;/).map((s) => s.trim()).filter(Boolean) : [],
      alternativas: q.tipo === 'objetiva' ? q.alternativas.filter((a) => a.texto.trim()) : []
    }))
    const av = await api(`/api/avaliacoes/${props.avaliacaoId}/questoes/lote`, { method: 'POST', body: { questoes, substituir: substituir.value } })
    emit('importado', { av, qtd: questoes.length, titulo: previa.value.titulo_sugerido })
  } catch (e) { erro.value = e.message } finally { gravando.value = false }
}
</script>

<template>
  <div class="modal-fundo">
    <div class="modal" style="max-width: 900px">
      <div class="cabecalho">
        <h2 style="margin: 0">Importar questões</h2>
        <button class="sec" @click="emit('fechar')">Fechar</button>
      </div>

      <template v-if="!previa">
        <p class="sub">Envie a prova em <b>Word (.docx)</b>, <b>PDF</b> (com texto, não escaneado) ou <b>.txt</b>, ou cole o texto.
          O sistema reconhece questões numeradas (<code>1)</code>, <code>2.</code>, <code>Questão 3</code>), alternativas com letra
          (<code>a)</code>, <code>(B)</code>) e o gabarito marcado com <code>*</code>, <code>(X)</code>, <b>negrito</b>,
          uma linha <code>Resposta: C</code> ou uma tabela <code>GABARITO 1-A 2-C…</code> no final.
          Questões sem alternativas viram dissertativas.</p>
        <p><a class="btn sec pequeno" href="/api/modelos/modelo-avaliacao.docx">⬇ Baixar modelo em Word</a></p>
        <div class="campo"><label>Arquivo</label><input type="file" accept=".docx,.pdf,.txt,.md,.doc" @change="ler" /></div>
        <div class="campo"><label>…ou cole o texto da prova</label>
          <textarea v-model="texto" rows="8" placeholder="1) Qual é a capital do Brasil?&#10;a) São Paulo&#10;b) Brasília *&#10;c) Salvador&#10;&#10;2) Explique o ciclo da água.&#10;Resposta esperada: ...&#10;Palavras-chave: evaporação; condensação; precipitação" @input="arquivo = null"></textarea></div>
        <button :disabled="!texto.trim() || lendo" @click="ler()">{{ lendo ? 'Lendo…' : 'Ler texto' }}</button>
        <p v-if="lendo" class="sub">Lendo o arquivo…</p>
      </template>

      <div v-if="erro" class="aviso erro" style="margin-top: .8rem">{{ erro }}</div>

      <template v-if="previa">
        <div class="aviso" :class="pendentes ? 'alerta' : 'ok'">
          Encontradas <b>{{ previa.questoes.length }}</b> questões
          ({{ previa.questoes.filter((q) => q.tipo === 'objetiva').length }} objetivas,
          {{ previa.questoes.filter((q) => q.tipo === 'dissertativa').length }} dissertativas).
          <span v-if="pendentes"> <b>{{ pendentes }}</b> sem gabarito: clique na alternativa correta nas questões destacadas.</span>
          <span v-else> Confira e ajuste o que precisar antes de gravar.</span>
        </div>

        <div class="lista">
          <div v-for="q in previa.questoes" :key="q.numero" class="card q" :class="{ fora: !q.incluir, falta: q.incluir && semGabarito(q) }">
            <div class="acoes" style="justify-content: space-between; margin-bottom: .4rem">
              <div class="acoes">
                <label class="check"><input type="checkbox" v-model="q.incluir" /> <b>Questão {{ q.numero }}</b></label>
                <select v-model="q.tipo" style="width: auto" @change="mudarTipo(q)">
                  <option value="objetiva">Objetiva</option><option value="dissertativa">Dissertativa</option></select>
                <span class="sub">peso</span><input type="number" step="any" min="0.1" v-model="q.peso" style="width: 75px" />
              </div>
            </div>
            <template v-if="q.incluir">
              <EditorTexto v-model="q.enunciado" :rows="2" />
              <div v-if="q.tipo === 'objetiva'" style="margin-top: .4rem">
                <div v-for="(a, i) in q.alternativas" :key="i" class="alt" :class="{ certa: a.correta }">
                  <input type="radio" :name="'c' + q.numero" :checked="a.correta" @change="marcar(q, i)" title="Alternativa correta" />
                  <b>{{ LETRAS[i] }})</b>
                  <EditorTexto linha v-model="a.texto" />
                  <button class="btn-link" title="Remover" @click="q.alternativas.splice(i, 1)">✕</button>
                </div>
                <button class="btn-link" @click="q.alternativas.push({ texto: '', correta: false })">+ alternativa</button>
              </div>
              <div v-else class="linha" style="margin-top: .4rem">
                <div><label>Resposta esperada</label><EditorTexto v-model="q.gabarito_texto" :rows="2" /></div>
                <div><label>Palavras-chave (uma por linha)</label><textarea v-model="q.palavras_txt" rows="2"></textarea></div>
              </div>
              <div v-if="q.explicacao" class="sub" style="margin-top: .3rem"><b>Explicação:</b> <TextoComImagens tag="span" :texto="q.explicacao" /></div>
              <div v-for="(w, i) in q.avisos" :key="i" class="sub aviso-q">⚠ {{ w }}</div>
            </template>
          </div>
        </div>

        <div class="rodape">
          <label v-if="temQuestoes" class="check"><input type="checkbox" v-model="substituir" /> Substituir as questões que já existem</label>
          <span v-else></span>
          <div class="acoes">
            <button class="sec" @click="previa = null">← Outro arquivo</button>
            <button :disabled="!incluidas.length || gravando" @click="gravar">
              {{ gravando ? 'Gravando…' : `Importar ${incluidas.length} questão(ões)` }}</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.lista { max-height: 58vh; overflow-y: auto; padding-right: .3rem; }
.q { margin-bottom: .6rem; background: var(--bg); }
.q.fora { opacity: .55; }
.q.falta { border-color: var(--alerta); background: var(--alerta-claro); }
.alt { display: flex; gap: .5rem; align-items: center; margin-bottom: .3rem; padding: .15rem .4rem; border-radius: 6px; }
.alt.certa { background: var(--ok-claro); }
.alt input:not([type=radio]) { padding: .35rem .5rem; }
.aviso-q { color: var(--alerta); margin-top: .3rem; }
.rodape { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; margin-top: .8rem;
  border-top: 1px solid var(--borda); padding-top: .8rem; }
</style>
