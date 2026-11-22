import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'

describe('StatusBadge', () => {
  it('renderiza o rotulo em portugues para OK', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'OK' } })

    expect(wrapper.text()).toBe('OK')
    expect(wrapper.classes()).toContain('status-badge--ok')
  })

  it('renderiza o rotulo em portugues para ATENCAO', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'ATENCAO' } })

    expect(wrapper.text()).toBe('Atenção')
    expect(wrapper.classes()).toContain('status-badge--atencao')
  })

  it('renderiza o rotulo em portugues para CRITICO', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'CRITICO' } })

    expect(wrapper.text()).toBe('Crítico')
    expect(wrapper.classes()).toContain('status-badge--critico')
  })
})
