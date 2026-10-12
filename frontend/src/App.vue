<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, salvarSessao, sessao, sair } from './api'

const route = useRoute()
const router = useRouter()
const ehProf = computed(() => ['admin', 'professor'].includes(sessao.usuario?.papel))
const emProva = computed(() => route.path.startsWith('/aluno/prova'))

// atualiza o perfil salvo no navegador (ex.: professor promovido a administrador, vínculos novos)
onMounted(async () => {
  if (!sessao.token) return
  try {
    const u = await api('/api/auth/me')
    const mudouPapel = u.papel !== sessao.usuario?.papel
    salvarSessao(sessao.token, u)
    if (mudouPapel) window.location.reload()
  } catch {}
})

async function trocarSenha() {
  const atual = prompt('Senha atual:')
  if (!atual) return
  const nova = prompt('Nova senha (mínimo 4 caracteres):')
  if (!nova) return
  try {
    await api('/api/auth/trocar-senha', { method: 'POST', body: { senha_atual: atual, nova_senha: nova } })
    alert('Senha alterada com sucesso.')
  } catch (e) { alert(e.message) }
}

function logout() {
  sair()
  router.push('/login')
}
</script>

<template>
  <header v-if="sessao.token && route.path !== '/login'" class="topo">
    <div class="topo-in">
      <router-link to="/" class="marca">📝 Avaliações</router-link>
      <nav v-if="ehProf">
        <router-link to="/painel">Avaliações</router-link>
        <router-link to="/analises">Análises</router-link>
        <router-link to="/cadastros">Cadastros</router-link>
      </nav>
      <nav v-else-if="!emProva">
        <router-link to="/aluno">Minhas avaliações</router-link>
      </nav>
      <div class="usuario">
        <span class="nome">{{ sessao.usuario?.nome }}</span>
        <button v-if="!emProva" class="btn-link" @click="trocarSenha">Trocar senha</button>
        <button v-if="!emProva" class="btn-link" @click="logout">Sair</button>
      </div>
    </div>
  </header>
  <main class="conteudo">
    <router-view />
  </main>
</template>
