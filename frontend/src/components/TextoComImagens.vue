<script setup>
// Mostra um texto de questão trocando os marcadores [imagem:CHAVE] pelas imagens.
// O texto nunca vira HTML (sem v-html): não há risco de código injetado.
// Clicar na imagem amplia dentro da própria página — não abre outra aba,
// então não conta como "saiu da prova" no monitoramento.
import { computed, ref } from 'vue'

const props = defineProps({ texto: { type: String, default: '' }, tag: { type: String, default: 'div' } })
const BASE = import.meta.env.VITE_API_URL || ''
const RE = /\[imagem:([0-9a-f]{16,40})\]/g

const partes = computed(() => {
  const out = []
  const t = props.texto || ''
  let ultimo = 0
  for (const m of t.matchAll(RE)) {
    if (m.index > ultimo) out.push({ texto: t.slice(ultimo, m.index) })
    out.push({ img: `${BASE}/api/imagens/${m[1]}` })
    ultimo = m.index + m[0].length
  }
  if (ultimo < t.length) out.push({ texto: t.slice(ultimo) })
  // remove a quebra de linha logo antes/depois da imagem (ela já fica em bloco próprio)
  return out.map((p, i) => p.texto === undefined ? p : {
    texto: p.texto.replace(out[i - 1]?.img ? /^\n/ : /$^/, '').replace(out[i + 1]?.img ? /\n$/ : /$^/, '')
  }).filter((p) => p.img || p.texto)
})
const ampliada = ref(null)
</script>

<template>
  <component :is="tag" class="texto-img">
    <template v-for="(p, i) in partes" :key="i">
      <img v-if="p.img" :src="p.img" class="img-questao" loading="lazy" alt="Imagem da questão (clique para ampliar)"
        title="Clique para ampliar" @click.stop.prevent="ampliada = p.img" />
      <span v-else>{{ p.texto }}</span>
    </template>
    <Teleport to="body">
    <div v-if="ampliada" class="img-zoom" @click="ampliada = null" role="dialog" aria-label="Imagem ampliada">
      <img :src="ampliada" alt="Imagem ampliada" />
      <span class="img-zoom-fechar">✕ fechar</span>
    </div>
    </Teleport>
  </component>
</template>

<style>
.texto-img { white-space: pre-wrap; }
.img-questao { display: block; max-width: 100%; max-height: 420px; height: auto; margin: .5rem 0; border-radius: 6px;
  border: 1px solid var(--borda, #ddd); cursor: zoom-in; background: #fff; }
label .img-questao, li .img-questao, td .img-questao { max-height: 220px; }
.img-zoom { position: fixed; inset: 0; z-index: 2000; background: rgba(0, 0, 0, .85); display: flex;
  align-items: center; justify-content: center; padding: 1rem; cursor: zoom-out; }
.img-zoom img { max-width: 100%; max-height: 100%; background: #fff; border-radius: 4px; }
.img-zoom-fechar { position: fixed; top: .75rem; right: 1rem; color: #fff; font-size: .95rem; }
</style>
