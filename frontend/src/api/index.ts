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

  // 数据库
  listDatabases: (connId: number) => http.get(`/databases/${connId}`) as Promise<ApiResponse<string[]>>,
  listSchemas: (connId: number, database?: string) =>
    http.get(`/databases/${connId}/schemas`, { params: { database } }) as Promise<ApiResponse<string[]>>,

  // 表
  listTables: (connId: number, database?: string, schema?: string) =>
    http.get(`/tables/${connId}`, { params: { database, schema } }) as Promise<ApiResponse<TableInfo[]>>,
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

  // SQL 执行
  executeSQL: (connId: number, sql: string, database?: string, schema?: string) =>
    http.post('/query/execute', { conn_id: connId, sql, database, schema }) as Promise<ApiResponse<ExecResult>>,
  executeBatch: (connId: number, sqls: { sql: string; params?: any[] }[], database?: string, schema?: string) =>
    http.post('/query/batch', { conn_id: connId, sqls, database, schema }) as Promise<ApiResponse>,
}