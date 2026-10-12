import { createRouter, createWebHistory } from 'vue-router'
import { sessao } from './api'

import Login from './views/Login.vue'
import QrCode from './views/QrCode.vue'
import Painel from './views/prof/Painel.vue'
import Cadastros from './views/prof/Cadastros.vue'
import AvaliacaoEditar from './views/prof/AvaliacaoEditar.vue'
import Resultados from './views/prof/Resultados.vue'
import Analises from './views/prof/Analises.vue'
import MinhasAvaliacoes from './views/aluno/MinhasAvaliacoes.vue'
import Responder from './views/aluno/Responder.vue'
import ResultadoAluno from './views/aluno/Resultado.vue'

const prof = { papeis: ['admin', 'professor'] }
const aluno = { papeis: ['aluno'] }

const routes = [
  { path: '/login', component: Login, meta: { publica: true } },
  { path: '/qrcode', component: QrCode, meta: { publica: true } },
  { path: '/', redirect: () => (sessao.usuario?.papel === 'aluno' ? '/aluno' : '/painel') },
  { path: '/painel', component: Painel, meta: prof },
  { path: '/cadastros', component: Cadastros, meta: prof },
  { path: '/analises', component: Analises, meta: prof },
  { path: '/avaliacoes/nova', component: AvaliacaoEditar, meta: prof },
  { path: '/avaliacoes/:id', component: AvaliacaoEditar, meta: prof, props: true },
  { path: '/avaliacoes/:id/resultados', component: Resultados, meta: prof, props: true },
  { path: '/aluno', component: MinhasAvaliacoes, meta: aluno },
  { path: '/aluno/prova/:id', component: Responder, meta: aluno, props: true },
  { path: '/aluno/resultado/:tid', component: ResultadoAluno, meta: aluno, props: true },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (to.meta.publica) return true
  // sem login: vai para o login e, depois de entrar, volta para onde ia (ex.: QR code → /aluno)
  if (!sessao.token) return { path: '/login', query: to.fullPath !== '/' ? { volta: to.fullPath } : {} }
  if (to.meta.papeis && !to.meta.papeis.includes(sessao.usuario?.papel)) return '/'
  return true
})

export default router
