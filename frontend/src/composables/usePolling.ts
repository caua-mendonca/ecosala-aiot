import { onUnmounted } from 'vue'

export function usePolling(callback: () => void | Promise<void>, intervalMs: number): void {
  void callback()

  const intervalId = window.setInterval(() => {
    void callback()
  }, intervalMs)

  onUnmounted(() => {
    window.clearInterval(intervalId)
  })
}
