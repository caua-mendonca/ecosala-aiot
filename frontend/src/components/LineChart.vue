<script setup lang="ts">
// Wrapper fino do Chart.js. Atualiza os dados no lugar (sem recriar o gráfico).
//  kind='line'    : séries com x = rótulo (hora) e y = valor
//  kind='scatter' : pontos {x, y} numéricos (previsto x real)
//  kind='bar'     : barras horizontais com rótulos (importância dos atributos)
import { Chart, registerables, type ChartConfiguration } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

Chart.register(...registerables)

export interface Series {
  label: string
  data: Array<{ x: string | number; y: number | null }>
  color?: string
  dashed?: boolean
}

const props = withDefaults(defineProps<{
  series: Series[]
  kind?: 'line' | 'scatter' | 'bar'
  minimal?: boolean
  yMin?: number
  yMax?: number
  xLabel?: string
  yLabel?: string
}>(), { kind: 'line', minimal: false })

const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null
const palette = ['#0f766e', '#2563eb', '#d97706', '#9333ea', '#dc2626', '#0891b2']

function labels(): string[] {
  return (props.series[0]?.data ?? []).map((p) => String(p.x))
}

function datasets(): any[] {
  return props.series.map((s, i) => {
    const color = s.color ?? palette[i % palette.length]
    return {
      label: s.label,
      data: props.kind === 'scatter' ? s.data : s.data.map((p) => p.y),
      borderColor: color,
      backgroundColor: props.kind === 'line' ? color + '22' : color + 'bb',
      borderDash: s.dashed ? [6, 4] : undefined,
      pointRadius: props.kind === 'scatter' ? 2 : 0,
      borderWidth: props.minimal ? 1.5 : 2,
      tension: 0.25,
      spanGaps: true,
      showLine: props.kind !== 'scatter' || !!s.dashed,
    }
  })
}

function build() {
  if (!canvas.value) return
  const scatter = props.kind === 'scatter'
  const bar = props.kind === 'bar'
  const cfg: ChartConfiguration = {
    type: scatter ? 'scatter' : bar ? 'bar' : 'line',
    data: { labels: scatter ? undefined : labels(), datasets: datasets() },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: bar ? 'y' : 'x',
      plugins: {
        legend: { display: !props.minimal && props.series.length > 1 },
        tooltip: { enabled: !props.minimal },
      },
      scales: {
        x: {
          display: !props.minimal,
          type: scatter || bar ? 'linear' : 'category',
          title: { display: !!props.xLabel, text: props.xLabel ?? '' },
          ticks: { maxTicksLimit: 8, autoSkip: true, maxRotation: 0 },
        },
        y: {
          display: !props.minimal,
          type: bar ? 'category' : 'linear',
          min: props.yMin,
          max: props.yMax,
          title: { display: !!props.yLabel, text: props.yLabel ?? '' },
        },
      },
    },
  }
  chart = new Chart(canvas.value, cfg)
}

watch(() => props.series, () => {
  if (!chart) return build()
  if (chart.data.datasets.length !== props.series.length) {
    chart.destroy()
    return build()
  }
  if (props.kind !== 'scatter') chart.data.labels = labels()
  const fresh = datasets()
  chart.data.datasets.forEach((ds, i) => { ds.data = fresh[i].data })
  chart.update('none')
})

onMounted(build)
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <canvas ref="canvas" />
</template>
