<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, salvarSessao } from '../api'

const router = useRouter()
const route = useRoute()
const modo = ref('entrar')        // entrar | cadastro
const login = ref('')
const senha = ref('')
const erro = ref('')
const carregando = ref(false)
const cfg = ref({ cadastro_aberto: false, exige_codigo: false })
const novo = ref({ nome: '', login: '', senha: '', senha2: '', codigo: '' })

onMounted(async () => { try { cfg.value = await api('/api/auth/config') } catch {} })

async function entrar() {
  erro.value = ''
  carregando.value = true
  try {
    const r = await api('/api/auth/login', { method: 'POST', body: { login: login.value, senha: senha.value } })
    salvarSessao(r.token, r.usuario)
    const volta = typeof route.query.volta === 'string' && route.query.volta.startsWith('/') && !route.query.volta.startsWith('//') ? route.query.volta : null
    const doAluno = volta?.startsWith('/aluno')
    router.push(volta && (r.usuario.papel === 'aluno') === !!doAluno ? volta : r.usuario.papel === 'aluno' ? '/aluno' : '/painel')
  } catch (e) {
    erro.value = e.message
  } finally {
    carregando.value = false
  }
}

async function cadastrar() {
  erro.value = ''
  if (novo.value.senha !== novo.value.senha2) return (erro.value = 'As senhas não conferem')
  carregando.value = true
  try {
    const r = await api('/api/auth/cadastro', { method: 'POST', body: {
      nome: novo.value.nome, login: novo.value.login, senha: novo.value.senha, codigo: novo.value.codigo || null } })
    salvarSessao(r.token, r.usuario)
    router.push('/cadastros')
  } catch (e) {
    erro.value = e.message
  } finally {
    carregando.value = false
  }
}
</script>

<template>
  <div class="login">
    <form v-if="modo === 'entrar'" class="card" @submit.prevent="entrar">
      <h1>📝 Avaliações Online</h1>
      <p class="sub" style="margin-bottom: 1.25rem">Entre com seu usuário (ou RM) e senha.</p>
      <div v-if="erro" class="aviso erro">{{ erro }}</div>
      <div class="campo">
        <label for="login">Usuário ou RM</label>
        <input id="login" v-model="login" autocomplete="username" autocapitalize="off" required />
      </div>
      <div class="campo">
        <label for="senha">Senha</label>
        <input id="senha" v-model="senha" type="password" autocomplete="current-password" required />
      </div>
      <button type="submit" :disabled="carregando" style="width: 100%; justify-content: center">
        {{ carregando ? 'Entrando…' : 'Entrar' }}
      </button>
      <p v-if="cfg.cadastro_aberto" class="sub" style="text-align: center; margin-top: 1rem">
        É professor e ainda não tem conta?
        <button type="button" class="btn-link" @click="modo = 'cadastro'; erro = ''">Criar conta de professor</button>
      </p>
    </form>

    <form v-else class="card" @submit.prevent="cadastrar">
      <h1>Criar conta de professor</h1>
      <p class="sub" style="margin-bottom: 1rem">Você terá uma área só sua para cadastrar escolas, disciplinas, turmas, alunos e avaliações.
        Alunos não se cadastram aqui: o professor importa a lista da turma.</p>
      <div v-if="erro" class="aviso erro">{{ erro }}</div>
      <div class="campo"><label>Nome completo</label><input v-model="novo.nome" required minlength="3" /></div>
      <div class="campo"><label>Usuário para entrar (sem espaços)</label>
        <input v-model="novo.login" required minlength="3" pattern="[A-Za-z0-9._@-]+" autocapitalize="off" placeholder="ex.: marcelo.santos" /></div>
      <div class="linha">
        <div class="campo"><label>Senha</label><input v-model="novo.senha" type="password" required minlength="6" autocomplete="new-password" /></div>
        <div class="campo"><label>Repita a senha</label><input v-model="novo.senha2" type="password" required minlength="6" autocomplete="new-password" /></div>
      </div>
      <div v-if="cfg.exige_codigo" class="campo"><label>Código de convite (fornecido pelo administrador)</label>
        <input v-model="novo.codigo" required /></div>
      <button type="submit" :disabled="carregando" style="width: 100%; justify-content: center">
        {{ carregando ? 'Criando…' : 'Criar conta e entrar' }}</button>
      <p style="text-align: center; margin-top: 1rem"><button type="button" class="btn-link" @click="modo = 'entrar'; erro = ''">← Já tenho conta</button></p>
    </form>
    <p class="versao"><router-link to="/qrcode">📱 QR code para os alunos entrarem pelo celular</router-link> · versão 19</p>
  </div>
</template>

<style scoped>
.login { min-height: 80vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.versao { color: var(--suave); font-size: .75rem; margin-top: .6rem; }
.login form { width: 100%; max-width: 420px; padding: 1.75rem; }
</style>
