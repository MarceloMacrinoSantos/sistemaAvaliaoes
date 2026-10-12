<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'
import Feedback from '../../components/Feedback.vue'

const props = defineProps({ tid: String })
const dados = ref(null)
const erro = ref('')

onMounted(async () => {
  try { dados.value = await api(`/api/aluno/tentativas/${props.tid}/resultado`) } catch (e) { erro.value = e.message }
})
</script>

<template>
  <router-link to="/aluno" class="sub">← Minhas avaliações</router-link>
  <div v-if="erro" class="aviso erro" style="margin-top: 1rem">{{ erro }}</div>
  <template v-if="dados">
    <h1 style="margin-top: .5rem">{{ dados.avaliacao.titulo }}</h1>
    <p class="sub" style="margin-bottom: 1rem">{{ dados.avaliacao.disciplina }} · Correção e feedback</p>
    <Feedback :dados="dados" />
  </template>
</template>
