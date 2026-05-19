import axios from 'axios'
import type { AxiosInstance } from 'axios'

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '网络错误'
    return Promise.reject(new Error(msg))
  },
)

// ── 类型 ─────────────────────────────────────────────

export interface ApiResponse<T = any> {
  success: boolean
  message?: string
  data?: T
}

export interface ConnInfo {
  id: number
  db_type: string
  name: string
  host: string
  port: number
  user: string
  database: string
  ssh_enabled: boolean
}

export interface ConnDetail extends ConnInfo {
  password: string
  ssh_host: string
  ssh_port: number
  ssh_user: string
  ssh_auth_type: string
  ssh_password: string
  ssh_key_path: string
  ssh_key_phrase: string
  ssh_local_port: number
  ssh_remote_host: string
  ssh_remote_port: number
}

export interface TableInfo {
  name: string
  comment: string
}

export interface ColumnDetail {
  Field: string
  Type: string
  Collation: string
  Null: string
  Key: string
  Default: string | null
  Extra: string
  Comment: string
}

export interface ExecResult {
  columns: string[]
  rows: any[][]
  affected: number
  is_query: boolean
  error?: string
}

// ── API 方法 ─────────────────────────────────────────

export const api = {
  // 连接管理
  listConnections: () => http.get('/connections/') as Promise<ApiResponse<ConnInfo[]>>,
  getConnection: (id: number) => http.get(`/connections/${id}`) as Promise<ApiResponse<ConnDetail>>,
  createConnection: (data: any) => http.post('/connections/', { data }) as Promise<ApiResponse<{ id: number }>>,
  updateConnection: (id: number, data: any) => http.put(`/connections/${id}`, { conn_id: id, data }) as Promise<ApiResponse>,
  deleteConnection: (id: number) => http.delete(`/connections/${id}`) as Promise<ApiResponse>,
  testConnection: (data: any) => http.post('/connections/test', { data }) as Promise<ApiResponse>,
  disconnectConnection: (connId: number) => http.post(`/connections/${connId}/disconnect`) as Promise<ApiResponse>,

  // 数据库
  listDatabases: (connId: number) => http.get(`/databases/${connId}`) as Promise<ApiResponse<string[]>>,
  createDatabase: (connId: number, dbName: string) => http.post(`/databases/${connId}`, { database: dbName }) as Promise<ApiResponse>,
  deleteDatabase: (connId: number, dbName: string) => http.delete(`/databases/${connId}/${encodeURIComponent(dbName)}`) as Promise<ApiResponse>,
  listSchemas: (connId: number, database?: string) =>
    http.get(`/databases/${connId}/schemas`, { params: { database } }) as Promise<ApiResponse<string[]>>,

  // 表
  listTables: (connId: number, database?: string, schema?: string) =>
    http.get(`/tables/${connId}`, { params: { database, schema }, timeout: 60000 }) as Promise<ApiResponse<TableInfo[]>>,
  getTableColumns: (connId: number, table: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/${table}/columns`, { params: { database, schema } }) as Promise<ApiResponse<ColumnDetail[]>>,
  getTableIndexes: (connId: number, table: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/${table}/indexes`, { params: { database, schema } }) as Promise<ApiResponse<any[]>>,
  getTableDDL: (connId: number, table: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/${table}/ddl`, { params: { database, schema } }) as Promise<ApiResponse<string>>,
  getPrimaryKeys: (connId: number, table: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/${table}/primary-keys`, { params: { database, schema } }) as Promise<ApiResponse<string[]>>,
  getRelations: (connId: number, database?: string) =>
    http.get(`/tables/${connId}/relations`, { params: { database } }) as Promise<ApiResponse<any[]>>,
  listViews: (connId: number, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/views`, { params: { database, schema } }) as Promise<ApiResponse<string[]>>,
  listFunctions: (connId: number, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/functions`, { params: { database, schema } }) as Promise<ApiResponse<any[]>>,

  // ── 视图管理 ──
  getViewDDL: (connId: number, viewName: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/views/${encodeURIComponent(viewName)}/ddl`, { params: { database, schema } }) as Promise<ApiResponse<string>>,

  // ── 函数管理 ──
  getFunctionDDL: (connId: number, funcName: string, funcType?: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/functions/${encodeURIComponent(funcName)}/ddl`, { params: { func_type: funcType, database, schema } }) as Promise<ApiResponse<string>>,
  getFunctionMetadata: (connId: number, funcName: string, database?: string, schema?: string) =>
    http.get(`/tables/${connId}/functions/${encodeURIComponent(funcName)}/metadata`, { params: { database, schema } }) as Promise<ApiResponse<any>>,

  // 表结构修改
  createTable: (connId: number, params: any) =>
    http.post(`/tables/${connId}/create`, params) as Promise<ApiResponse>,
  dropTable: (connId: number, table: string, database?: string, schema?: string) =>
    http.delete(`/tables/${connId}/${table}`, { params: { database, schema } }) as Promise<ApiResponse>,
  renameTable: (connId: number, table: string, newName: string, database?: string, schema?: string) =>
    http.put(`/tables/${connId}/${table}/rename`, { new_name: newName, database, schema }) as Promise<ApiResponse>,
  addColumn: (connId: number, table: string, params: any) =>
    http.post(`/tables/${connId}/${table}/columns`, params) as Promise<ApiResponse>,
  modifyColumn: (connId: number, table: string, columnName: string, params: any) =>
    http.put(`/tables/${connId}/${table}/columns/${columnName}`, params) as Promise<ApiResponse>,
  dropColumn: (connId: number, table: string, columnName: string, database?: string, schema?: string) =>
    http.delete(`/tables/${connId}/${table}/columns/${columnName}`, { params: { database, schema } }) as Promise<ApiResponse>,

  // ── 导出 ───────────────────────────────────────────

  /** 导出表结构 - 返回 blob，需触发下载 */
  exportStructure: (params: any) =>
    http.post('/export/structure', params, { responseType: 'blob' }) as Promise<Blob>,

  /** 导出 ER 图 - 返回 blob */
  exportER: (params: any) =>
    http.post('/export/er', params, { responseType: 'blob' }) as Promise<Blob>,

  /** 导出 Navicat 连接 */
  exportNavicat: (params: any) =>
    http.post('/export/navicat', params, { responseType: 'blob' }) as Promise<Blob>,

  /** 导出表数据 */
  exportData: (params: any) =>
    http.post('/export/data', params, { responseType: 'blob' }) as Promise<Blob>,

  // ── 同步 ───────────────────────────────────────────

  syncStart: (params: any) =>
    http.post('/sync/start', params) as Promise<ApiResponse<{ task_id: string }>>,
  syncProgress: (taskId: string) =>
    http.get(`/sync/progress/${taskId}`) as Promise<ApiResponse<{
      task_id: string
      status: string
      progress: { table: string; index: number; total: number; percent: number }
      logs: { message: string; level: string }[]
      result: any
      record_id: number | null
      log_path: string
      error: string
    }>>,
  syncCancel: (taskId: string) =>
    http.post(`/sync/cancel/${taskId}`) as Promise<ApiResponse>,
  syncHistory: (limit?: number) =>
    http.get('/sync/history', { params: { limit } }) as Promise<ApiResponse<any[]>>,
  syncHistoryDetail: (id: number) =>
    http.get(`/sync/history/${id}`) as Promise<ApiResponse<any>>,

  // ── 备份 ───────────────────────────────────────────

  backupCreate: (connId: number, params: any) =>
    http.post(`/backup/${connId}/backup`, params) as Promise<ApiResponse<{ file_path: string; file_size: number; tables_count: number }>>,
  backupRestore: (connId: number, params: any) =>
    http.post(`/backup/${connId}/restore`, params) as Promise<ApiResponse>,
  backupList: (connId: number) =>
    http.get(`/backup/${connId}/backups`) as Promise<ApiResponse<any[]>>,
  backupDelete: (filename: string) =>
    http.delete(`/backup/backups/${encodeURIComponent(filename)}`) as Promise<ApiResponse>,

  // ── 导入 ───────────────────────────────────────────

  /** 上传并解析导入文件 */
  importParse: (formData: FormData) =>
    http.post('/import/parse', formData) as Promise<ApiResponse<{
      file_path: string
      columns: string[]
      preview_rows: any[][]
      total_rows: number
    }>>,

  /** 上传 SQL 文件并直接执行 */
  importSQL: (formData: FormData) =>
    http.post('/import/sql', formData) as Promise<ApiResponse<{ affected: number; errors: string[] }>>,

  /** 执行导入到数据库 */
  importExecute: (params: any) =>
    http.post('/import/execute', params) as Promise<ApiResponse<{ affected: number }>>,

  // ── AI 助手 ───────────────────────────────────────────

  /** 获取 AI 配置列表 */
  aiListConfigs: () =>
    http.get('/ai/configs') as Promise<ApiResponse<any[]>>,

  /** 获取默认 AI 配置 */
  aiDefaultConfig: () =>
    http.get('/ai/configs/default') as Promise<ApiResponse>,

  /** 创建 AI 配置 */
  aiCreateConfig: (data: any) =>
    http.post('/ai/configs', data) as Promise<ApiResponse<{ id: number }>>,

  /** 更新 AI 配置 */
  aiUpdateConfig: (id: number, data: any) =>
    http.put(`/ai/configs/${id}`, data) as Promise<ApiResponse>,

  /** 删除 AI 配置 */
  aiDeleteConfig: (id: number) =>
    http.delete(`/ai/configs/${id}`) as Promise<ApiResponse>,

  /** 测试 AI 配置连接 */
  aiTestConfig: (id: number) =>
    http.post(`/ai/configs/${id}/test`) as Promise<ApiResponse>,

  /** 获取模型列表 */
  aiListModels: (apiKey: string, baseUrl: string) =>
    http.post('/ai/models', { api_key: apiKey, base_url: baseUrl }) as Promise<ApiResponse<string[]>>,

  /** 构建数据库上下文 */
  aiBuildContext: (data: any) =>
    http.post('/ai/context', data, { timeout: 120000 }) as Promise<ApiResponse<{ context: string; tables: number; db_type: string; db_name: string }>>,

  /** 获取聊天历史列表 */
  aiListHistory: () =>
    http.get('/ai/history') as Promise<ApiResponse<any[]>>,

  /** 获取聊天历史详情 */
  aiGetHistory: (id: number) =>
    http.get(`/ai/history/${id}`) as Promise<ApiResponse>,

  /** 保存聊天历史 */
  aiSaveHistory: (data: any) =>
    http.post('/ai/history', data) as Promise<ApiResponse<{ id: number }>>,

  /** 删除聊天历史 */
  aiDeleteHistory: (id: number) =>
    http.delete(`/ai/history/${id}`) as Promise<ApiResponse>,

  // SQL 执行
  executeSQL: (connId: number, sql: string, database?: string, schema?: string, signal?: AbortSignal) =>
    http.post('/query/execute', { conn_id: connId, sql, database, schema_name: schema }, { signal }) as Promise<ApiResponse<ExecResult>>,
  executeBatch: (connId: number, sqls: { sql: string; params?: any[] }[], database?: string, schema?: string) =>
    http.post('/query/batch', { conn_id: connId, sqls, database, schema_name: schema }) as Promise<ApiResponse>,
}