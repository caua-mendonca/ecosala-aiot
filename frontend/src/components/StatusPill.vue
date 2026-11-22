<script setup lang="ts">
import type { ItemStatus } from '../types'
import { STATUS_LABEL } from '../utils/format'

defineProps<{ status: ItemStatus; label?: string }>()
</script>

<template>
  <span class="pill" :class="status">{{ label ?? STATUS_LABEL[status] }}</span>
</template>
