<script setup>
import { ref } from 'vue'
import { fmtData, fmtDuracao } from '../api'

// Metadados de acesso e linha do tempo da tentativa (visto pelo professor e pelo aluno).
defineProps({ m: Object, professor: Boolean })
const aberto = ref(false)

const ICONE = {
  inicio: '▶', retomada: '↻', outro_dispositivo: '⚠', saiu_aba: '↗', saiu_janela: '↗', voltou: '↩',
  fechou: '✕', envio: '✓', envio_automatico: '⏱'
}
const ALERTA = new Set(['outro_dispositivo', 'saiu_aba', 'saiu_janela', 'fechou'])
const hora = (iso) => new Date(iso).toLocaleTimeString('pt-BR')
</script>

<template>
  <div class="card monit" :class="{ alerta: m.alerta }">
    <div class="cabecalho" style="margin-bottom: .6rem">
      <h3 style="margin: 0">🔒 Monitoramento da avaliação</h3>
      <span v-if="!m.alerta" class="tag ok">Nenhuma saída registrada</span>
      <span v-else class="tag alerta">Ocorrências registradas</span>
    </div>

    <div class="indicadores">
      <div><span class="sub">Saídas da aba/janela</span><strong :class="{ ruim: m.qtd_saidas }">{{ m.qtd_saidas }}</strong></div>
      <div><span class="sub">Tempo fora da prova</span><strong :class="{ ruim: m.tempo_fora_seg }">{{ fmtDuracao(m.tempo_fora_seg) }}</strong></div>
      <div><span class="sub">Fechou/recarregou</span><strong :class="{ ruim: m.qtd_fechamentos }">{{ m.qtd_fechamentos }}</strong></div>
      <div><span class="sub">Outro navegador/dispositivo</span><strong :class="{ ruim: m.outro_dispositivo }">{{ m.outro_dispositivo ? 'Sim' : 'Não' }}</strong></div>
      <div><span class="sub">Tempo total</span><strong>{{ fmtDuracao(m.tempo_gasto_seg) }}</strong></div>
    </div>

    <table class="meta">
      <tr><td class="sub">Início</td><td>{{ fmtData(m.iniciado_em) }}</td>
        <td class="sub">Envio</td><td>{{ fmtData(m.enviado_em) }}</td></tr>
      <tr><td class="sub">Navegador</td><td>{{ m.navegador_inicio }}</td>
        <td class="sub">IP</td><td><code>{{ m.ip_inicio || '—' }}</code>
          <span v-if="m.ip_envio && m.ip_envio !== m.ip_inicio" class="tag alerta" title="IP diferente no envio">envio: {{ m.ip_envio }}</span></td></tr>
      <tr v-if="professor"><td class="sub">Tela</td><td>{{ m.tela || '—' }}</td>
        <td class="sub">Acessos</td><td>{{ m.qtd_acessos }}</td></tr>
    </table>

    <button v-if="m.eventos?.length" class="btn-link" @click="aberto = !aberto">
      {{ aberto ? '▾' : '▸' }} Linha do tempo ({{ m.eventos.length }} registros)
    </button>
    <ol v-if="aberto" class="linha-tempo">
      <li v-for="(e, i) in m.eventos" :key="i" :class="{ ev_alerta: ALERTA.has(e.tipo) }">
        <span class="ic">{{ ICONE[e.tipo] || '•' }}</span>
        <span class="h">{{ hora(e.em) }}</span>
        <span>{{ e.rotulo }}<template v-if="e.duracao_seg != null"> — ficou fora {{ fmtDuracao(e.duracao_seg) }}</template>
          <small v-if="professor && (e.navegador || e.ip)" class="sub"> · {{ e.navegador }} {{ e.ip }}</small></span>
      </li>
    </ol>
    <p v-if="!professor" class="sub" style="margin: .5rem 0 0; font-size: .85rem">
      Estes registros também foram enviados ao seu professor.
    </p>
  </div>
</template>

<style scoped>
.monit { border-left: 4px solid var(--ok); }
.monit.alerta { border-left-color: var(--alerta); }
.indicadores { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .6rem; margin-bottom: .75rem; }
.indicadores > div { background: var(--bg); border-radius: 8px; padding: .5rem .7rem; display: flex; flex-direction: column; }
.indicadores .sub { font-size: .78rem; }
.indicadores strong { font-size: 1.15rem; }
.indicadores strong.ruim { color: var(--alerta); }
.meta td { padding: .3rem .4rem; font-size: .88rem; border-bottom: none; }
.linha-tempo { list-style: none; padding: 0; margin: .5rem 0 0; font-size: .9rem; }
.linha-tempo li { display: flex; gap: .6rem; padding: .3rem 0; border-bottom: 1px dashed var(--borda); }
.linha-tempo .ic { width: 1.2rem; text-align: center; }
.linha-tempo .h { font-variant-numeric: tabular-nums; color: var(--suave); min-width: 4.8rem; }
.linha-tempo li.ev_alerta { color: var(--alerta); }
</style>
