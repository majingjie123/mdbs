<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../api'

const message = useMessage()
const dialog = useDialog()

const props = defineProps<{
  connId: number
}>()

const users = ref<any[]>([])
const loading = ref(false)
const selectedUser = ref<any>(null)
const grantText = ref('')

// 对话框
const showCreateDialog = ref(false)
const showGrantDialog = ref(false)
const createLoading = ref(false)
const grantLoading = ref(false)
const newUser = ref({ user: '', host: '%', password: '' })
const grantForm = ref({ user: '', host: '%', database: '*', table: '*', privilege: 'ALL PRIVILEGES', with_grant: false })

const privilegeOptions = [
  'ALL PRIVILEGES', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE',
  'DROP', 'ALTER', 'INDEX', 'REFERENCES', 'TRIGGER', 'CREATE VIEW',
  'SHOW VIEW', 'CREATE ROUTINE', 'ALTER ROUTINE', 'EXECUTE', 'EVENT',
  'LOCK TABLES', 'CREATE TEMPORARY TABLES',
]

async function loadUsers() {
  loading.value = true
  try {
    const res: any = await api.listUsers(props.connId)
    if (res.success) {
      users.value = res.data || []
    } else {
      message.error(res.message || '加载用户列表失败')
    }
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function selectUser(user: any) {
  selectedUser.value = user
  grantText.value = user.grants?.join('\n') || '暂无权限'
}

async function doCreateUser() {
  if (!newUser.value.user) {
    message.warning('请输入用户名')
    return
  }
  createLoading.value = true
  try {
    const res: any = await api.createUser(props.connId, newUser.value)
    if (res.success) {
      message.success(res.message || '创建成功')
      showCreateDialog.value = false
      newUser.value = { user: '', host: '%', password: '' }
      await loadUsers()
    } else {
      message.error(res.message || '创建失败')
    }
  } catch (e: any) {
    message.error(e.message || '创建失败')
  } finally {
    createLoading.value = false
  }
}

function confirmDrop(user: any) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除用户 "${user.user}@${user.host}" 吗？\n此操作不可撤销！`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.dropUser(props.connId, user.user, user.host)
        if (res.success) {
          message.success(res.message || '删除成功')
          if (selectedUser.value?.user === user.user) {
            selectedUser.value = null
            grantText.value = ''
          }
          await loadUsers()
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error(e.message || '删除失败')
      }
    },
  })
}

function openGrantDialog(user: any) {
  grantForm.value = {
    user: user.user,
    host: user.host,
    database: '*',
    table: '*',
    privilege: 'ALL PRIVILEGES',
    with_grant: false,
  }
  showGrantDialog.value = true
}

async function doGrant() {
  grantLoading.value = true
  try {
    const res: any = await api.grantPrivilege(props.connId, grantForm.value)
    if (res.success) {
      message.success(res.message || '授权成功')
      showGrantDialog.value = false
      // 刷新用户数据
      await loadUsers()
      if (selectedUser.value?.user === grantForm.value.user) {
        selectUser(selectedUser.value)
      }
    } else {
      message.error(res.message || '授权失败')
    }
  } catch (e: any) {
    message.error(e.message || '授权失败')
  } finally {
    grantLoading.value = false
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<template>
  <div class="user-manager">
    <div class="header">
      <h2>👤 用户权限管理</h2>
      <n-space size="small">
        <n-button size="tiny" type="primary" @click="showCreateDialog = true">新建用户</n-button>
        <n-button size="tiny" @click="loadUsers">刷新</n-button>
      </n-space>
    </div>

    <div class="body">
      <!-- 用户列表 -->
      <div class="user-list-panel">
        <n-spin :show="loading">
          <n-list v-if="users.length > 0" bordered>
            <n-list-item
              v-for="u in users"
              :key="u.user + u.host"
              :class="{ active: selectedUser?.user === u.user && selectedUser?.host === u.host }"
              @click="selectUser(u)"
              style="cursor: pointer;"
            >
              <template #prefix>
                <n-tag
                  :type="u.account_locked ? 'error' : 'success'"
                  size="tiny"
                  round
                >
                  {{ u.account_locked ? '锁定' : '正常' }}
                </n-tag>
              </template>
              <n-thing>
                <template #header>{{ u.user }}</template>
                <template #description>
                  <span style="font-size: 11px;">{{ u.host }}</span>
                </template>
              </n-thing>
              <template #suffix>
                <n-button-group size="tiny">
                  <n-button size="tiny" @click.stop="openGrantDialog(u)">授权</n-button>
                  <n-button size="tiny" type="error" @click.stop="confirmDrop(u)" :disabled="u.user === 'root'">删除</n-button>
                </n-button-group>
              </template>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无用户数据" />
        </n-spin>
      </div>

      <!-- 权限详情 -->
      <div class="grant-detail-panel">
        <template v-if="selectedUser">
          <n-descriptions :title="`${selectedUser.user}@${selectedUser.host}`" bordered size="small" :column="1">
            <n-descriptions-item label="用户名">{{ selectedUser.user }}</n-descriptions-item>
            <n-descriptions-item label="主机">{{ selectedUser.host }}</n-descriptions-item>
            <n-descriptions-item label="账户状态">
              <n-tag :type="selectedUser.account_locked ? 'error' : 'success'" size="small">
                {{ selectedUser.account_locked ? '已锁定' : '正常' }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="密码过期" v-if="selectedUser.password_expired !== undefined">
              {{ selectedUser.password_expired ? '是' : '否' }}
            </n-descriptions-item>
          </n-descriptions>

          <n-divider />

          <div class="grants-section">
            <div class="grants-header">
              <span style="font-weight: 600;">权限列表</span>
              <n-button size="tiny" @click="openGrantDialog(selectedUser)">授予权限</n-button>
            </div>
            <n-pre class="grants-pre">{{ grantText }}</n-pre>
          </div>
        </template>
        <n-empty v-else description="请从左侧选择一个用户" style="margin-top: 60px;" />
      </div>
    </div>

    <!-- 新建用户对话框 -->
    <n-modal v-model:show="showCreateDialog" title="新建用户" preset="card" style="width: 400px;" :mask-closable="false">
      <n-space vertical>
        <n-input v-model:value="newUser.user" placeholder="用户名" />
        <n-input v-model:value="newUser.host" placeholder="主机 (默认 %)" />
        <n-input v-model:value="newUser.password" type="password" show-password-on="click" placeholder="密码 (可选)" />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCreateDialog = false">取消</n-button>
          <n-button type="primary" @click="doCreateUser" :loading="createLoading">创建</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 授权对话框 -->
    <n-modal v-model:show="showGrantDialog" title="授予权限" preset="card" style="width: 480px;" :mask-closable="false">
      <n-space vertical>
        <n-input v-model:value="grantForm.database" placeholder="数据库 (* 表示所有)" />
        <n-input v-model:value="grantForm.table" placeholder="表 (* 表示所有)" />
        <n-select v-model:value="grantForm.privilege" :options="privilegeOptions.map(p => ({ label: p, value: p }))" />
        <n-checkbox v-model:checked="grantForm.with_grant">WITH GRANT OPTION (允许继续授权)</n-checkbox>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showGrantDialog = false">取消</n-button>
          <n-button type="primary" @click="doGrant" :loading="grantLoading">授权</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.user-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.header h2 {
  margin: 0;
  font-size: 18px;
}

.body {
  display: flex;
  flex: 1;
  gap: 12px;
  overflow: hidden;
}

.user-list-panel {
  width: 350px;
  min-width: 280px;
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
  padding-right: 8px;
}

.grant-detail-panel {
  flex: 1;
  overflow-y: auto;
}

.user-list-panel .n-list-item.active {
  background-color: var(--color-primary-opacity-1);
  border-radius: 4px;
}

.grants-section {
  margin-top: 8px;
}

.grants-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.grants-pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
