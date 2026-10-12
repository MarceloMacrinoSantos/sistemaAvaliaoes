<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Chart from 'chart.js/auto'

// Wrapper simples do Chart.js com o estilo do sistema (marcas finas, grade discreta, tooltip ao passar o mouse).
const props = defineProps({ tipo: { type: String, default: 'bar' }, dados: Object, opcoes: Object, altura: { type: Number, default: 280 } })
const canvas = ref(null)
let grafico = null

const TEXTO = '#52514e'
const GRADE = '#ebeae6'

function base() {
  return {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
    interaction: { mode: 'nearest', intersect: false },
    plugins: {
      legend: { labels: { color: TEXTO, boxWidth: 12, boxHeight: 12, usePointStyle: true, font: { size: 12 } } },
      tooltip: { backgroundColor: '#1d2330', padding: 10, cornerRadius: 6, titleFont: { weight: '600' } }
    },
    scales: {
      x: { ticks: { color: TEXTO, font: { size: 11 } }, grid: { display: false }, border: { color: GRADE } },
      y: { ticks: { color: TEXTO, font: { size: 11 } }, grid: { color: GRADE }, border: { display: false } }
    }
  }
}
function mesclar(a, b) {
  for (const k of Object.keys(b || {})) {
    if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k]) && a[k] && typeof a[k] === 'object') mesclar(a[k], b[k])
    else a[k] = b[k]
  }
  return a
}
function desenhar() {
  grafico?.destroy()
  if (!canvas.value || !props.dados) return
  grafico = new Chart(canvas.value, { type: props.tipo, data: props.dados, options: mesclar(base(), props.opcoes) })
}
onMounted(desenhar)
watch(() => [props.dados, props.opcoes], desenhar, { deep: true })
onBeforeUnmount(() => grafico?.destroy())
</script>

<template>
  <div :style="{ position: 'relative', height: altura + 'px' }"><canvas ref="canvas"></canvas></div>
</template>
