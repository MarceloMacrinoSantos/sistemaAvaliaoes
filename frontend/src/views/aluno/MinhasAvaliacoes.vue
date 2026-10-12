<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, fmtData, sessao } from '../../api'

const router = useRouter()
const lista = ref([])
const confirmar = ref(null)
const ciente = ref(false)
function iniciar(av) { ciente.value = false; confirmar.value = av }
const erro = ref('')
const carregando = ref(true)
const SIT = {
  disponivel: ['Disponível', 'ok'], em_andamento: ['Em andamento', 'alerta'], agendada: ['Agendada', 'cinza'],
  enviada: ['Enviada', ''], perdida: ['Não realizada', 'erro']
}
const TIPO = { prova: 'Prova', simulado: 'Simulado', teste: 'Teste' }
const fmt = (n) => (Math.round(n * 100) / 100).toLocaleString('pt-BR')

onMounted(async () => {
  try { lista.value = await api('/api/aluno/avaliacoes') } catch (e) { erro.value = e.message } finally { carregando.value = false }
})
</script>

<template>
  <div class="cabecalho">
    <div>
      <h1>Olá, {{ sessao.usuario?.nome?.split(' ')[0] }}!</h1>
      <p class="sub">{{ sessao.usuario?.turma }} · {{ sessao.usuario?.escola }}</p>
    </div>
  </div>
  <div v-if="erro" class="aviso erro">{{ erro }}</div>

  <div class="grade">
    <div v-for="av in lista" :key="av.id" class="card" style="margin: 0; display: flex; flex-direction: column">
      <div class="acoes" style="margin-bottom: .4rem">
        <span class="tag" :class="SIT[av.situacao][1]">{{ SIT[av.situacao][0] }}</span>
        <small class="sub">{{ TIPO[av.tipo] }} · {{ av.disciplina }} · {{ av.turma }}</small>
      </div>
      <h3>{{ av.titulo }}</h3>
      <small class="sub">{{ av.qtd_questoes }} questões<span v-if="av.duracao_min"> · {{ av.duracao_min }} min</span></small>
      <small class="sub">De {{ fmtData(av.inicio) }} até {{ fmtData(av.fim) }}</small>
      <div style="margin-top: auto; padding-top: .9rem">
        <button v-if="av.situacao === 'disponivel'" @click="iniciar(av)">Iniciar</button>
        <router-link v-else-if="av.situacao === 'em_andamento'" class="btn" :to="`/aluno/prova/${av.id}`">Continuar</router-link>
        <template v-else-if="av.situacao === 'enviada'">
          <router-link v-if="av.resultado_disponivel" class="btn sec" :to="`/aluno/resultado/${av.tentativa_id}`">
            Ver correção · {{ fmt(av.nota) }}/{{ fmt(av.nota_max) }}
          </router-link>
          <small v-else class="sub">Correção disponível após {{ fmtData(av.fim) }}</small>
        </template>
      </div>
    </div>
  </div>
  <p v-if="!carregando && !lista.length" class="vazio card">Nenhuma avaliação para sua turma no momento.</p>

  <div v-if="confirmar" class="modal-fundo" @click.self="confirmar = null">
    <div class="modal" style="max-width: 520px">
      <h2>{{ confirmar.titulo }}</h2>
      <ul class="regras">
        <li>{{ confirmar.qtd_questoes }} questões, valendo {{ confirmar.nota_total }} pontos no total.</li>
        <li v-if="confirmar.duracao_min">Você terá <strong>{{ confirmar.duracao_min }} minutos</strong> a partir de agora. Ao fim do tempo a prova é enviada automaticamente.</li>
        <li>Suas respostas são salvas automaticamente.</li>
      </ul>
      <div v-if="confirmar.monitorar" class="aviso alerta">
        <strong>🔒 Esta avaliação é monitorada.</strong> Durante a prova serão registrados:
        <ul style="margin: .4rem 0 0; padding-left: 1.2rem">
          <li>data e hora de início e envio, navegador, dispositivo e endereço IP;</li>
          <li>cada vez que você trocar de aba, minimizar ou clicar em outra janela, e quanto tempo ficou fora;</li>
          <li>se fechar ou recarregar a página, ou abrir a prova em outro navegador/dispositivo.</li>
        </ul>
        Esses registros serão enviados ao professor. Mantenha apenas esta aba aberta até enviar.
      </div>
      <label v-if="confirmar.monitorar" class="check" style="margin-bottom: .8rem">
        <input type="checkbox" v-model="ciente" /> Li e estou ciente do monitoramento
      </label>
      <div class="acoes">
        <button :disabled="confirmar.monitorar && !ciente" @click="router.push(`/aluno/prova/${confirmar.id}`)">Começar agora</button>
        <button class="sec" @click="confirmar = null">Cancelar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.regras { padding-left: 1.2rem; margin: 0 0 1rem; }
.regras li { margin-bottom: .25rem; }
</style>
