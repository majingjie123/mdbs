<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useMessage, useDialog } from 'naive-ui'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const connId = computed(() => parseInt(route.params.id as string))
const isNew = computed(() => connId.value === 0)

const formRef = ref()
const formValue = ref({
  name: '',
  db_type: 'MySQL',
  host: '127.0.0.1',
  port: 3306,
  user: 'root',
  password: '',
  database: '',
  ssh_enabled: false,
  ssh_host: '',
  ssh_port: 22,
  ssh_user: '',
  ssh_auth_type: 'password',
  ssh_password: '',
  ssh_key_path: '',
  ssh_key_phrase: '',
  ssh_local_port: 0,
  ssh_remote_host: '',
  ssh_remote_port: 0,
})

const saving = ref(false)
const testing = ref(false)
const sshTesting = ref(false)
const keyFileInput = ref<HTMLInputElement | null>(null)

function browseKeyFile() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pem,.ppk,.key,*'
  input.onchange = (e: any) => {
    const file = e.target?.files?.[0]
    if (file) {
      // 浏览器安全限制，不能获取完整路径，只显示文件名
      formValue.value.ssh_key_path = file.name
      message.info(`已选择文件: ${file.name}（请在路径中填入完整路径）`)
    }
  }
  input.click()
}

async function testSshConn() {
  sshTesting.value = true
  try {
    // 使用 testConnection 但只检查 SSH 隧道
    const res: any = await api.testConnection({ ...formValue.value, database: '' })
    if (res.success) {
      message.success('SSH 连接成功！')
    } else {
      message.error(`SSH 连接失败: ${res.message}`)
    }
  } catch (e: any) {
    message.error(e.message)
  } finally {
    sshTesting.value = false
  }
}

const dbTypeOptions = [
  { label: 'MySQL / MariaDB', value: 'MySQL' },
  { label: 'PostgreSQL', value: 'PostgreSQL' },
]

onMounted(async () => {
  if (!isNew.value) {
    const res: any = await api.getConnection(connId.value)
    if (res.success && res.data) {
      const d = res.data
      formValue.value = {
        name: d.name || '',
        db_type: d.db_type || 'MySQL',
        host: d.host || '127.0.0.1',
        port: d.port || 3306,
        user: d.user || 'root',
        password: d.password || '',
        database: d.database || '',
        ssh_enabled: !!d.ssh_enabled,
        ssh_host: d.ssh_host || '',
        ssh_port: d.ssh_port || 22,
        ssh_user: d.ssh_user || '',
        ssh_auth_type: d.ssh_auth_type || 'password',
        ssh_password: d.ssh_password || '',
        ssh_key_path: d.ssh_key_path || '',
        ssh_key_phrase: d.ssh_key_phrase || '',
        ssh_local_port: d.ssh_local_port || 0,
        ssh_remote_host: d.ssh_remote_host || '',
        ssh_remote_port: d.ssh_remote_port || 0,
      }
    }
  }
})

async function testConn() {
  testing.value = true
  try {
    const res: any = await api.testConnection(formValue.value)
    if (res.success) {
      message.success('连接成功！')
    } else {
      message.error(`连接失败: ${res.message}`)
    }
  } catch (e: any) {
    message.error(e.message)
  } finally {
    testing.value = false
  }
}

async function save() {
  saving.value = true
  try {
    if (isNew.value) {
      await api.createConnection(formValue.value)
      message.success('创建成功')
    } else {
      await api.updateConnection(connId.value, formValue.value)
      message.success('更新成功')
    }
    router.push('/connections')
  } catch (e: any) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

function remove() {
  dialog.warning({
    title: '确认删除',
    content: '确定删除此连接？',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.deleteConnection(connId.value)
      message.success('已删除')
      router.push('/connections')
    },
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ isNew ? '新建连接' : '编辑连接' }}</h2>
      <n-space>
        <n-button @click="router.push('/connections')">返回</n-button>
        <n-button v-if="!isNew" type="error" @click="remove">删除</n-button>
      </n-space>
    </div>

    <n-form ref="formRef" :model="formValue" label-placement="left" label-width="120" class="form">
      <n-form-item label="连接名称" path="name">
        <n-input v-model:value="formValue.name" placeholder="给连接起个名字" />
      </n-form-item>
      <n-form-item label="数据库类型" path="db_type">
        <n-select v-model:value="formValue.db_type" :options="dbTypeOptions" />
      </n-form-item>
      <n-form-item label="主机地址" path="host">
        <n-input v-model:value="formValue.host" placeholder="127.0.0.1" />
      </n-form-item>
      <n-form-item label="端口" path="port">
        <n-input-number v-model:value="formValue.port" :min="1" :max="65535" />
      </n-form-item>
      <n-form-item label="用户名" path="user">
        <n-input v-model:value="formValue.user" placeholder="root" />
      </n-form-item>
      <n-form-item label="密码" path="password">
        <n-input v-model:value="formValue.password" type="password" show-password-on="click" />
      </n-form-item>
      <n-form-item label="默认数据库" path="database">
        <n-input v-model:value="formValue.database" placeholder="留空则不指定" />
      </n-form-item>

      <n-divider />
      <div class="ssh-header">
        <n-form-item label="SSH 隧道">
          <n-switch v-model:value="formValue.ssh_enabled" />
        </n-form-item>
        <n-button v-if="formValue.ssh_enabled" size="tiny" :loading="sshTesting" @click="testSshConn" type="primary" ghost>
          测试 SSH 连接
        </n-button>
      </div>

      <template v-if="formValue.ssh_enabled">
        <n-form-item label="SSH 主机">
          <n-input v-model:value="formValue.ssh_host" />
        </n-form-item>
        <n-form-item label="SSH 端口">
          <n-input-number v-model:value="formValue.ssh_port" :min="1" :max="65535" />
        </n-form-item>
        <n-form-item label="SSH 用户">
          <n-input v-model:value="formValue.ssh_user" />
        </n-form-item>
        <n-form-item label="认证方式">
          <n-select
            v-model:value="formValue.ssh_auth_type"
            :options="[
              { label: '密码', value: 'password' },
              { label: '私钥', value: 'key' },
            ]"
          />
        </n-form-item>
        <n-form-item v-if="formValue.ssh_auth_type === 'password'" label="SSH 密码">
          <n-input v-model:value="formValue.ssh_password" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item v-if="formValue.ssh_auth_type === 'key'" label="私钥路径">
          <n-input v-model:value="formValue.ssh_key_path" placeholder="C:/Users/xxx/.ssh/id_rsa" />
          <n-button size="tiny" @click="browseKeyFile" style="margin-left: 4px">浏览</n-button>
        </n-form-item>
        <n-form-item v-if="formValue.ssh_auth_type === 'key'" label="私钥密码">
          <n-input v-model:value="formValue.ssh_key_phrase" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item label="远程主机">
          <n-input v-model:value="formValue.ssh_remote_host" placeholder="127.0.0.1" />
        </n-form-item>
        <n-form-item label="远程端口">
          <n-input-number v-model:value="formValue.ssh_remote_port" :min="1" :max="65535" placeholder="3306" />
        </n-form-item>
      </template>

      <div class="form-actions">
        <n-button type="primary" :loading="testing" @click="testConn">测试连接</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </div>
    </n-form>
  </div>
</template>

<style scoped>
.page {
  padding: 24px;
  overflow-y: auto;
  height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  color: #e0e0e0;
}

.form {
  max-width: 600px;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.ssh-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
