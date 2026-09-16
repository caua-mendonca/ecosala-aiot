<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import type { Reading } from '@/domain/Reading'
import { formatDateTimeShort } from '@/utils/formatDate'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

const props = defineProps<{
  readings: Reading[]
  metric: 'temperature' | 'humidity' | 'luminosity'
  unit: string
  referenceMin?: number
  referenceMax?: number
}>()

const chartData = computed<ChartData<'line'>>(() => {
  const labels = props.readings.map((reading) => formatDateTimeShort(reading.timestamp))
  const values = props.readings.map((reading) => reading[props.metric])

  const datasets: ChartData<'line'>['datasets'] = [
    {
      label: props.unit,
      data: values,
      borderColor: '#2563eb',
      backgroundColor: 'rgba(37, 99, 235, 0.15)',
      tension: 0.3,
      pointRadius: 2,
    },
  ]

  if (props.referenceMin !== undefined) {
    const referenceMin = props.referenceMin
    datasets.push({
      label: 'Mínimo ideal',
      data: labels.map(() => referenceMin),
      borderColor: '#dc2626',
      borderDash: [6, 6],
      pointRadius: 0,
      borderWidth: 1,
    })
  }

  if (props.referenceMax !== undefined) {
    const referenceMax = props.referenceMax
    datasets.push({
      label: 'Máximo ideal',
      data: labels.map(() => referenceMax),
      borderColor: '#dc2626',
      borderDash: [6, 6],
      pointRadius: 0,
      borderWidth: 1,
    })
  }

  return { labels, datasets }
})

const chartOptions: ChartOptions<'line'> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true, position: 'bottom' },
  },
}
</script>

<template>
  <div class="reading-line-chart">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.reading-line-chart {
  position: relative;
  height: 260px;
}
</style>
