<script setup>
import { computed } from 'vue'
import TextoComImagens from './TextoComImagens.vue'
import { ROTULO_SITUACAO } from '../api'
import Monitoramento from './Monitoramento.vue'

// Relatório de correção questão a questão, usado pelo aluno e pelo professor.
const props = defineProps({ dados: Object, revisavel: Boolean })
const emit = defineEmits(['revisar', 'aceitar-ia'])

const LETRAS = 'ABCDEFGHIJ'
const CLASSE = { certa: 'ok', errada: 'erro', parcial: 'alerta', em_branco: 'cinza', pendente: 'cinza' }
const ICONE = { certa: '✓', errada: '✗', parcial: '◐', em_branco: '—', pendente: '⏳' }
const pct = computed(() => props.dados.nota_max ? Math.round((100 * props.dados.nota) / props.dados.nota_max) : 0)
const contagem = computed(() => {
  const c = { certa: 0, errada: 0, parcial: 0, em_branco: 0, pendente: 0 }
  props.dados.questoes.forEach((q) => c[q.situacao]++)
  return c
})
const fmt = (n) => (n == null ? '—' : (Math.round(n * 100) / 100).toLocaleString('pt-BR'))
</script>

<template>
  <div class="card resumo">
    <div>
      <div class="sub">Nota</div>
      <div class="nota">{{ fmt(dados.nota) }} <small>/ {{ fmt(dados.nota_max) }}</small></div>
      <div class="barra" style="margin-top: .4rem"><span :style="{ width: pct + '%' }"></span></div>
    </div>
    <div class="contagem">
      <span class="tag ok">✓ {{ contagem.certa }} certa(s)</span>
      <span class="tag erro">✗ {{ contagem.errada }} errada(s)</span>
      <span v-if="contagem.parcial" class="tag alerta">◐ {{ contagem.parcial }} parcial(is)</span>
      <span v-if="contagem.em_branco" class="tag cinza">— {{ contagem.em_branco }} em branco</span>
      <span v-if="contagem.pendente" class="tag cinza">⏳ {{ contagem.pendente }} aguardando correção</span>
    </div>
  </div>
  <div v-if="dados.envio_automatico" class="aviso alerta">A avaliação foi enviada automaticamente ao fim do tempo.</div>
  <Monitoramento v-if="dados.monitoramento" :m="dados.monitoramento" :professor="revisavel" />

  <article v-for="q in dados.questoes" :key="q.questao_id" class="card questao" :class="'q-' + q.situacao">
    <div class="cabecalho" style="margin-bottom: .5rem">
      <strong>Questão {{ q.numero }}</strong>
      <div class="acoes">
        <span class="tag" :class="CLASSE[q.situacao]">{{ ICONE[q.situacao] }} {{ ROTULO_SITUACAO[q.situacao] }}</span>
        <span class="sub">{{ fmt(q.pontos) }} / {{ fmt(q.pontos_max) }} pt</span>
      </div>
    </div>
    <TextoComImagens class="enunciado" :texto="q.enunciado" />

    <template v-if="q.tipo === 'objetiva'">
      <div v-for="(a, i) in q.alternativas" :key="a.id" class="alternativa"
        :class="{ certa: a.correta, errada: a.marcada && !a.correta }" style="cursor: default">
        <span class="letra">{{ LETRAS[i] }})</span>
        <TextoComImagens tag="span" style="flex: 1" :texto="a.texto" />
        <small v-if="a.marcada && a.correta"><strong>Sua resposta ✓</strong></small>
        <small v-else-if="a.marcada"><strong>Sua resposta ✗</strong></small>
        <small v-else-if="a.correta"><strong>Resposta correta</strong></small>
      </div>
    </template>
    <template v-else>
      <label>Resposta do aluno</label>
      <div class="resposta-texto">{{ q.resposta_texto || '(em branco)' }}</div>
      <template v-if="q.gabarito">
        <label style="margin-top: .6rem">Resposta esperada</label>
        <TextoComImagens class="resposta-texto gabarito" :texto="q.gabarito" />
      </template>
      <div v-if="revisavel && q.ia && q.ia.modo !== 'desligada' && q.ia.status" class="caixa-ia-resp">
        <div class="acoes" style="justify-content: space-between">
          <strong>🤖 Correção por IA</strong>
          <span v-if="q.ia.status === 'ok'" class="tag ok">{{ fmt(q.ia.pontos) }} / {{ fmt(q.pontos_max) }} pt</span>
          <span v-else-if="q.ia.status === 'falhou'" class="tag alerta" :title="q.ia.erro">IA indisponível — vale palavras-chave</span>
          <span v-else class="tag cinza">⏳ corrigindo…</span>
        </div>
        <p v-if="q.ia.status === 'ok'" style="margin: .3rem 0">{{ q.ia.feedback }}</p>
        <p v-if="q.ia.status === 'falhou'" class="sub" style="margin: .3rem 0">Motivo: {{ q.ia.erro }}</p>
        <small class="sub">Palavras-chave: {{ fmt(q.ia.pontos_chaves) }} pt<template v-if="q.ia.provedor"> · {{ q.ia.provedor }}</template>
          <template v-if="q.ia.status === 'ok' && Math.abs((q.ia.pontos || 0) - (q.ia.pontos_chaves || 0)) >= q.pontos_max * 0.4">
            · <strong style="color: var(--alerta)">as duas correções discordam bastante: confira</strong></template></small>
        <div v-if="q.ia.status === 'ok' && q.resposta_id && q.pontos !== q.ia.pontos" style="margin-top: .4rem">
          <button class="pequeno" @click="emit('aceitar-ia', q)">Usar a nota da IA ({{ fmt(q.ia.pontos) }})</button>
        </div>
      </div>
      <p v-if="q.feedback && q.situacao !== 'em_branco'" class="sub" style="margin: .5rem 0 0">
        <strong>Correção automática:</strong> {{ q.feedback }}
        <span v-if="q.revisado"> · <em>nota revisada pelo professor</em></span>
      </p>
    </template>

    <div v-if="q.explicacao" class="aviso info" style="margin: .75rem 0 0"><strong>Explicação:</strong> <TextoComImagens tag="span" :texto="q.explicacao" /></div>
    <div v-if="q.comentario_professor" class="aviso ok" style="margin: .6rem 0 0"><strong>Comentário do professor:</strong> {{ q.comentario_professor }}</div>

    <div v-if="revisavel && q.resposta_id" style="margin-top: .75rem">
      <button class="sec pequeno" @click="emit('revisar', q)">Ajustar nota / comentar</button>
    </div>
  </article>
</template>

<style scoped>
.resumo { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; align-items: center; }
.resumo > div:first-child { min-width: 200px; }
.nota { font-size: 2rem; font-weight: 700; line-height: 1.1; }
.nota small { font-size: 1rem; color: var(--suave); font-weight: 500; }
.contagem { display: flex; gap: .4rem; flex-wrap: wrap; }
.questao { border-left: 4px solid var(--borda); }
.q-certa { border-left-color: var(--ok); }
.q-errada { border-left-color: var(--erro); }
.q-parcial { border-left-color: var(--alerta); }
.resposta-texto { white-space: pre-wrap; background: var(--bg); border: 1px solid var(--borda); border-radius: 8px; padding: .6rem .8rem; }
.gabarito { background: var(--ok-claro); border-color: #bfe3cf; }
.caixa-ia-resp { margin-top: .6rem; padding: .55rem .7rem; border: 1px dashed var(--borda, #ccc); border-radius: 8px; }
</style>
