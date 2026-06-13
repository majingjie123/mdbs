<script setup lang="ts">
import { ref, onMounted, h } from "vue"
import { useMessage, useDialog } from "naive-ui"
import { api } from "../api"

const props = defineProps<{ connId: number; dbName?: string |>()
const message = useMessage()
const dialog = useDialog()
const tasks = ref<any[]>([])
const loading = ref(false)
const showFormDialog = ref(false)
const editingTask = ref<any>(null)
const saving = ref(false)

const form = ref({
  conn_id: props.connId,
  name: "",
  database: props.dbName || "",
  sql_text: "",
  schedule_type: "once",
  schedule_value: "",
  enabled: true,
})

async function loadTasks() {
  loading.value = true
  try {
    const res: any = await api.sqlTaskList(props.connId)
    if (res.success) tasks.value = res.data || []
    else message.error(res.message)
  } catch (e: any) { message.error(e.message) }
  finally { loading.value = false }
}

function openNew() {
  editingTask.value = null
  form.value = { conn_id: props.connId, name: "", database: props.dbName || "", sql_text: "", schedule_type: "once", schedule_value: "", enabled: true }
  showFormDialog.value = true
}

function openEdit(task: any) {
  editingTask.value = task
  form.value = {
    conn_id: task.conn_id,
    name: task.name,
    database: task.database || "",
    sql_text: task.sql_text,
    schedule_type: task.schedule_type || "once",
    schedule_value: task.schedule_value || "",
    enabled: task.enabled,
  }
  showFormDialog.value = true
}
