<script setup>
// QR code para os alunos entrarem no sistema pelo celular. Pode ser projetado na sala ou impresso.
import { computed, onMounted, ref, watch } from 'vue'
import QRCode from 'qrcode'
import { api } from '../api'

const props = defineProps({ pagina: Boolean })
const emit = defineEmits(['fechar'])
const enderecos = ref([])
const escolhido = ref('')
const imagem = ref('')
const copiado = ref(false)
const erro = ref('')

const link = computed(() => (escolhido.value ? escolhido.value.replace(/\/$/, '') + '/aluno' : ''))
const ehLocal = computed(() => /^https?:\/\/(localhost|127\.)/.test(escolhido.value))

onMounted(async () => {
  try {
    enderecos.value = (await api('/api/acesso')).enderecos
  } catch { enderecos.value = [window.location.origin] }
  escolhido.value = enderecos.value[0] || window.location.origin
})

watch(link, async (url) => {
  if (!url) return
  try {
    imagem.value = await QRCode.toDataURL(url, { width: 900, margin: 2, errorCorrectionLevel: 'M', color: { dark: '#111111', light: '#ffffff' } })
  } catch (e) { erro.value = 'Não foi possível gerar o QR code.' }
})

async function copiar() {
  try { await navigator.clipboard.writeText(link.value); copiado.value = true; setTimeout(() => (copiado.value = false), 2000) } catch {}
}
function telaCheia() {
  const el = document.querySelector('.qr-caixa')
  if (document.fullscreenElement) document.exitFullscreen()
  else el?.requestFullscreen?.()
}
function imprimir() { window.print() }
</script>

<template>
  <div :class="pagina ? 'qr-pagina' : 'modal-fundo qr-fundo'" @click.self="!pagina && emit('fechar')">
    <div class="qr-caixa card">
      <h2 class="qr-titulo">📱 Entre pelo celular</h2>
      <p class="qr-instr">Abra a câmera do celular, aponte para o código e toque no link.<br />
        Entre com seu <strong>RM</strong> e sua <strong>senha</strong>.</p>
      <img v-if="imagem" :src="imagem" class="qr-img" alt="QR code de acesso ao sistema" />
      <div v-if="erro" class="aviso erro">{{ erro }}</div>
      <p class="qr-link">{{ link }}</p>

      <div class="qr-acoes nao-imprimir">
        <select v-if="enderecos.length > 1" v-model="escolhido" title="Este computador tem mais de uma rede">
          <option v-for="e in enderecos" :key="e" :value="e">{{ e }}</option>
        </select>
        <button type="button" class="sec pequeno" @click="copiar">{{ copiado ? '✓ Copiado' : 'Copiar link' }}</button>
        <button type="button" class="sec pequeno" @click="telaCheia">Tela cheia</button>
        <button type="button" class="sec pequeno" @click="imprimir">Imprimir</button>
        <button v-if="!pagina" type="button" class="pequeno" @click="emit('fechar')">Fechar</button>
        <router-link v-else to="/" class="btn pequeno">Voltar ao sistema</router-link>
      </div>
      <p v-if="enderecos.length > 1" class="sub nao-imprimir" style="margin: .5rem 0 0">
        Se o celular não abrir, escolha outro endereço na lista (o computador tem mais de uma rede).</p>
      <p v-if="ehLocal" class="aviso alerta nao-imprimir" style="margin: .5rem 0 0">
        Este endereço só funciona neste computador. Conecte-o à rede da sala para gerar o endereço dos alunos.</p>
      <p class="sub nao-imprimir" style="margin: .5rem 0 0">O celular precisa estar na mesma rede (Wi-Fi) deste computador,
        a não ser que o sistema esteja publicado na internet.</p>
    </div>
  </div>
</template>

<style scoped>
.qr-fundo { z-index: 1500; }
.qr-pagina { min-height: 90vh; display: flex; align-items: center; justify-content: center; }
.qr-caixa { text-align: center; max-width: 640px; width: 100%; margin: auto; background: #fff; }
.qr-caixa:fullscreen { max-width: none; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.qr-caixa:fullscreen .qr-img { width: min(70vh, 90vw); }
.qr-caixa:fullscreen .qr-titulo { font-size: 3rem; }
.qr-caixa:fullscreen .qr-instr { font-size: 1.6rem; }
.qr-caixa:fullscreen .qr-link { font-size: 2.2rem; }
.qr-titulo { margin: 0 0 .25rem; font-size: 1.6rem; }
.qr-instr { margin: 0 0 .5rem; font-size: 1.05rem; }
.qr-img { width: min(380px, 80vw); height: auto; image-rendering: pixelated; }
.qr-link { font-family: Consolas, monospace; font-size: 1.35rem; font-weight: 700; word-break: break-all; margin: .25rem 0 .75rem; }
.qr-acoes { display: flex; gap: .5rem; justify-content: center; flex-wrap: wrap; align-items: center; }
.qr-acoes select { width: auto; }
@media print {
  .nao-imprimir { display: none !important; }
  .qr-caixa { box-shadow: none; border: none; }
  .qr-img { width: 12cm; }
}
</style>
