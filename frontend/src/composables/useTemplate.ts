import { ref } from "vue"

const STORAGE_KEY = "mdbs_io_templates"

export interface IOTemplate {
  id: string
  name: string
  type: "export" | "import"
  data: Record<string, any>
  createdAt: string
}

export function useTemplate(type: "export" | "import") {
  const templates = ref<IOTemplate[]>([])

  function loadTemplates() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const all: IOTemplate[] = raw ? JSON.parse(raw) : []
      templates.value = all.filter((t) => t.type === type)
    } catch {
      templates.value = []
    }
  }

  function saveTemplate(name: string, data: Record<string, any>) {
    const raw = localStorage.getItem(STORAGE_KEY)
    const all: IOTemplate[] = raw ? JSON.parse(raw) : []
    const existing = all.findIndex((t) => t.type === type && t.name === name)
    const tmpl: IOTemplate = {
      id: Date.now().toString(36),
      name,
      type,
      data,
      createdAt: new Date().toISOString(),
    }
    if (existing >= 0) {
      all[existing] = tmpl
    } else {
      all.push(tmpl)
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
    templates.value = all.filter((t) => t.type === type)
  }

  function deleteTemplate(id: string) {
    const raw = localStorage.getItem(STORAGE_KEY)
    const all: IOTemplate[] = raw ? JSON.parse(raw) : []
    const filtered = all.filter((t) => t.id !== id)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered))
    templates.value = filtered.filter((t) => t.type === type)
  }

  loadTemplates()

  return { templates, loadTemplates, saveTemplate, deleteTemplate }
}
