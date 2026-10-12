<script setup>
// Campo de texto de questão com suporte a imagens:
// botão "Imagem", colar (Ctrl+V) um print ou arrastar um arquivo para o campo.
// A imagem é enviada ao servidor e, no texto, entra o marcador [imagem:CHAVE] na posição do cursor.
import { computed, ref } from 'vue'
import { enviarArquivo } from '../api'
import TextoComImagens from './TextoComImagens.vue'

const props = defineProps({
  modelValue: { type: String, default: '' }, rows: { type: Number, default: 3 },
  linha: Boolean, placeholder: String, required: Boolean
})
const emit = defineEmits(['update:modelValue'])
const campo = ref(null)
const seletor = ref(null)
const enviando = ref(false)
const erro = ref('')
const temImagem = computed(() => /\[imagem:[0-9a-f]{16,40}\]/.test(props.modelValue || ''))

function inserir(marcador) {
  const el = campo.value
  const v = props.modelValue || ''
  const ini = el ? el.selectionStart ?? v.length : v.length
  const fim = el ? el.selectionEnd ?? v.length : v.length
  // em campo de várias linhas a imagem fica em linha própria
  const antes = props.linha || !v.slice(0, ini) || v.slice(0, ini).endsWith('\n') ? '' : '\n'
  const depois = props.linha || v.slice(fim).startsWith('\n') ? (props.linha ? ' ' : '') : '\n'
  const novo = v.slice(0, ini) + antes + marcador + depois + v.slice(fim)
  emit('update:modelValue', novo)
  const pos = ini + antes.length + marcador.length + depois.length
  requestAnimationFrame(() => { if (el) { el.focus(); el.setSelectionRange(pos, pos) } })
}

async function enviar(arquivos) {
  erro.value = ''
  const imgs = [...arquivos].filter((f) => f.type.startsWith('image/'))
  if (!imgs.length) return
  enviando.value = true
  try {
    for (const f of imgs) {
      const r = await enviarArquivo('/api/imagens', { arquivo: f })
      inserir(r.marcador)
    }
  } catch (e) { erro.value = e.message } finally { enviando.value = false }
}

function colar(ev) {
  const arquivos = [...(ev.clipboardData?.files || [])]
  if (arquivos.some((f) => f.type.startsWith('image/'))) { ev.preventDefault(); enviar(arquivos) }
}
function soltar(ev) {
  const arquivos = [...(ev.dataTransfer?.files || [])]
  if (arquivos.length) { ev.preventDefault(); enviar(arquivos) }
}
function escolhido(ev) { enviar(ev.target.files); ev.target.value = '' }
</script>

<template>
  <div class="editor-texto" :class="{ linha }">
    <div class="editor-linha">
      <input v-if="linha" ref="campo" :value="modelValue" :placeholder="placeholder" :required="required"
        @input="emit('update:modelValue', $event.target.value)" @paste="colar" @drop="soltar" @dragover.prevent />
      <textarea v-else ref="campo" :value="modelValue" :rows="rows" :placeholder="placeholder" :required="required"
        @input="emit('update:modelValue', $event.target.value)" @paste="colar" @drop="soltar" @dragover.prevent></textarea>
      <button type="button" class="sec pequeno btn-img" :disabled="enviando" @click="seletor.click()"
        :title="'Inserir imagem na posição do cursor (também dá para colar com Ctrl+V ou arrastar o arquivo)'">
        {{ enviando ? '⏳' : '🖼' }}<span v-if="!linha"> Imagem</span></button>
      <input ref="seletor" type="file" accept="image/*" multiple hidden @change="escolhido" />
    </div>
    <small v-if="erro" class="erro-img">{{ erro }}</small>
    <div v-if="temImagem" class="previa-img">
      <small class="sub">Prévia (como o aluno verá):</small>
      <TextoComImagens :texto="modelValue" />
    </div>
  </div>
</template>

<style scoped>
.editor-texto { width: 100%; }
.editor-linha { display: flex; gap: .4rem; align-items: flex-start; }
.editor-linha > input, .editor-linha > textarea { flex: 1; min-width: 0; }
.btn-img { white-space: nowrap; flex-shrink: 0; }
.erro-img { color: var(--erro, #c0392b); display: block; margin-top: .2rem; }
.previa-img { margin-top: .4rem; padding: .5rem .6rem; border: 1px dashed var(--borda, #ccc); border-radius: 6px; }
.linha .previa-img :deep(.img-questao) { max-height: 140px; }
</style>
