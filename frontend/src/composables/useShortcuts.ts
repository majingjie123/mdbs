/**
 * 快捷键配置 composable
 * 存储于 localStorage，所有组件共享
 */
import { ref, watch } from 'vue'

export const SHORTCUTS_KEY = 'mdbs_shortcuts'

// 默认快捷键定义
export interface ShortcutDef {
  id: string
  label: string
  /** CodeMirror key format: Mod-Enter, F5, Ctrl-... */
  defaultKey: string
  scope: 'editor' | 'global' | 'app'
  description: string
}

export const DEFAULT_SHORTCUTS: ShortcutDef[] = [
  { id: 'execute', label: '执行 SQL', defaultKey: 'Mod-Enter', scope: 'editor', description: '执行当前 SQL 查询' },
  { id: 'execute_f5', label: '执行 (F5)', defaultKey: 'F5', scope: 'editor', description: '执行当前 SQL 查询' },
  { id: 'format', label: '格式化 SQL', defaultKey: 'Mod-Shift-f', scope: 'editor', description: '格式化 SQL 代码' },
  { id: 'save', label: '保存草稿', defaultKey: 'Mod-s', scope: 'editor', description: '保存当前 SQL 到草稿' },
  { id: 'new_tab', label: '新建标签', defaultKey: 'Mod-n', scope: 'editor', description: '打开新的查询标签' },
  { id: 'close_tab', label: '关闭标签', defaultKey: 'Mod-w', scope: 'editor', description: '关闭当前标签页' },
]

export type ShortcutMap = Record<string, string>

/** 加载用户自定义快捷键映射 */
export function loadShortcuts(): ShortcutMap {
  try {
    const raw = localStorage.getItem(SHORTCUTS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return {}
}

/** 保存快捷键映射 */
export function saveShortcuts(map: ShortcutMap) {
  localStorage.setItem(SHORTCUTS_KEY, JSON.stringify(map))
}

/** 重置快捷键到默认 */
export function resetShortcuts() {
  localStorage.removeItem(SHORTCUTS_KEY)
}

/** 获取某个快捷键的当前值（用户自定义优先，否则默认） */
export function getShortcut(id: string): string {
  const custom = loadShortcuts()
  if (custom[id]) return custom[id]
  const def = DEFAULT_SHORTCUTS.find(s => s.id === id)
  return def?.defaultKey || ''
}

/** 构建 CodeMirror keymap 条目数组 */
export function buildKeymapEntries(customMap: ShortcutMap): Array<{ key: string; run: () => boolean }> {
  // 这个函数由 SqlEditor 调用，传回按键到 action 的映射
  // 但由于 ref 依赖，我们直接把逻辑写在 SqlEditor 里
  return []
}
