import { onUnmounted } from 'vue'

/**
 * Executa `callback` imediatamente e depois a cada `intervalMs`, limpando o
 * intervalo automaticamente quando o componente que o chamou e desmontado.
 */
export function usePolling(callback: () => void | Promise<void>, intervalMs: number): void {
  void callback()

  const intervalId = window.setInterval(() => {
    void callback()
  }, intervalMs)

  onUnmounted(() => {
    window.clearInterval(intervalId)
  })
}
