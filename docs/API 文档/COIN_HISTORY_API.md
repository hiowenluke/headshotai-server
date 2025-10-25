# 金币历史记录 API 文档

## 概述

本文档描述金币充值历史和消费历史相关的 API 接口，用于在客户端展示用户的金币交易记录。

## 认证要求

所有 API 都需要用户登录认证，通过 Cookie 中的 `app_session` 传递。

## API 端点

### 1. 获取充值历史

获取用户的金币充值记录。

**端点**: `GET /api/coins/topup-history`

**Query Parameters**:
- `limit` (可选): 返回记录数量，默认 20，最大 100
- `offset` (可选): 偏移量，默认 0，用于分页
- `status` (可选): 过滤状态，可选值：
  - `pending` - 待处理
  - `completed` - 已完成
  - `expired` - 已过期
  - `canceled` - 已取消

**请求示例**:
```http
GET /api/coins/topup-history?limit=20&offset=0&status=completed
Cookie: app_session=xxx
```

**响应示例**:
```json
{
  "items": [
    {
      "id": "1cdc4a22-4752-4d0e-80e3-4bc524506acd",
      "created_at": "2025-10-26T12:30:00Z",
      "amount_usd": 99.99,
      "coins_purchased": 1000,
      "coins_bonus": 200,
      "coins_total": 1200,
      "status": "completed",
      "payment_provider": "stripe",
      "payment_tx_id": "cs_test_xxx"
    },
    {
      "id": "2d955d6e-c59c-4776-903d-4ef520ee37c7",
      "created_at": "2025-10-25T10:15:00Z",
      "amount_usd": 49.99,
      "coins_purchased": 500,
      "coins_bonus": 50,
      "coins_total": 550,
      "status": "completed",
      "payment_provider": "stripe",
      "payment_tx_id": "cs_test_yyy"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

**字段说明**:
- `id`: 充值记录 ID
- `created_at`: 创建时间（ISO 8601 格式）
- `amount_usd`: 支付金额（美元）
- `coins_purchased`: 购买的金币数量
- `coins_bonus`: 赠送的金币数量
- `coins_total`: 总金币数量（购买 + 赠送）
- `status`: 充值状态
- `payment_provider`: 支付提供商（如 stripe）
- `payment_tx_id`: 支付交易 ID

**错误响应**:
```json
// 401 - 未认证
{
  "error": "not_authenticated"
}

// 404 - 用户不存在
{
  "error": "user_not_found"
}

// 400 - 参数错误
{
  "error": "invalid_parameters"
}

// 503 - 数据库不可用
{
  "error": "database_unavailable"
}
```

---

### 2. 获取消费历史

获取用户的金币消费记录。

**端点**: `GET /api/coins/spending-history`

**Query Parameters**:
- `limit` (可选): 返回记录数量，默认 20，最大 100
- `offset` (可选): 偏移量，默认 0，用于分页

**请求示例**:
```http
GET /api/coins/spending-history?limit=20&offset=0
Cookie: app_session=xxx
```

**响应示例**:
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "created_at": "2025-10-26T14:20:00Z",
      "service_name": "AI Headshot Generation",
      "service_quantity": 1,
      "coin_unit_price": 100,
      "coins_spent": 100,
      "product_name": "Headshot AI"
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "created_at": "2025-10-26T13:15:00Z",
      "service_name": "AI Headshot Generation",
      "service_quantity": 2,
      "coin_unit_price": 100,
      "coins_spent": 200,
      "product_name": "Headshot AI"
    }
  ],
  "total": 48,
  "limit": 20,
  "offset": 0
}
```

**字段说明**:
- `id`: 消费记录 ID
- `created_at`: 创建时间（ISO 8601 格式）
- `service_name`: 服务名称
- `service_quantity`: 服务数量
- `coin_unit_price`: 单价（金币）
- `coins_spent`: 消费的金币总数
- `product_name`: 产品名称

**错误响应**: 同充值历史 API

---

### 3. 获取金币统计摘要

获取用户的金币统计信息。

**端点**: `GET /api/coins/summary`

**请求示例**:
```http
GET /api/coins/summary
Cookie: app_session=xxx
```

**响应示例**:
```json
{
  "current_balance": 1200,
  "total_purchased": 5000,
  "total_bonus": 1000,
  "total_spent": 4800,
  "total_topups": 5,
  "total_spendings": 48
}
```

**字段说明**:
- `current_balance`: 当前余额
- `total_purchased`: 累计购买的金币（不含赠送）
- `total_bonus`: 累计赠送的金币
- `total_spent`: 累计消费的金币
- `total_topups`: 充值次数（仅已完成）
- `total_spendings`: 消费次数

**错误响应**: 同充值历史 API

---

## 客户端集成指南

### Vue 3 + TypeScript 示例

#### 1. 创建 API 服务

```typescript
// src/services/coinHistoryService.ts
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5010'

export interface TopupHistoryItem {
  id: string
  created_at: string
  amount_usd: number
  coins_purchased: number
  coins_bonus: number
  coins_total: number
  status: 'pending' | 'completed' | 'expired' | 'canceled'
  payment_provider: string
  payment_tx_id: string
}

export interface SpendingHistoryItem {
  id: string
  created_at: string
  service_name: string
  service_quantity: number
  coin_unit_price: number
  coins_spent: number
  product_name: string
}

export interface CoinSummary {
  current_balance: number
  total_purchased: number
  total_bonus: number
  total_spent: number
  total_topups: number
  total_spendings: number
}

export interface HistoryResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

class CoinHistoryService {
  private axios = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true, // 重要：携带 Cookie
    headers: {
      'Content-Type': 'application/json'
    }
  })

  /**
   * 获取充值历史
   */
  async getTopupHistory(params?: {
    limit?: number
    offset?: number
    status?: 'pending' | 'completed' | 'expired' | 'canceled'
  }): Promise<HistoryResponse<TopupHistoryItem>> {
    const response = await this.axios.get('/api/coins/topup-history', { params })
    return response.data
  }

  /**
   * 获取消费历史
   */
  async getSpendingHistory(params?: {
    limit?: number
    offset?: number
  }): Promise<HistoryResponse<SpendingHistoryItem>> {
    const response = await this.axios.get('/api/coins/spending-history', { params })
    return response.data
  }

  /**
   * 获取金币统计摘要
   */
  async getCoinSummary(): Promise<CoinSummary> {
    const response = await this.axios.get('/api/coins/summary')
    return response.data
  }
}

export const coinHistoryService = new CoinHistoryService()
```

#### 2. 创建 Composable（可选）

```typescript
// src/composables/useCoinHistory.ts
import { ref, computed } from 'vue'
import { coinHistoryService, type TopupHistoryItem, type SpendingHistoryItem, type CoinSummary } from '@/services/coinHistoryService'

export function useCoinHistory() {
  const topupHistory = ref<TopupHistoryItem[]>([])
  const spendingHistory = ref<SpendingHistoryItem[]>([])
  const summary = ref<CoinSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 分页状态
  const topupPagination = ref({
    total: 0,
    limit: 20,
    offset: 0
  })

  const spendingPagination = ref({
    total: 0,
    limit: 20,
    offset: 0
  })

  // 计算属性
  const hasMoreTopups = computed(() => 
    topupPagination.value.offset + topupPagination.value.limit < topupPagination.value.total
  )

  const hasMoreSpendings = computed(() => 
    spendingPagination.value.offset + spendingPagination.value.limit < spendingPagination.value.total
  )

  /**
   * 加载充值历史
   */
  async function loadTopupHistory(append = false) {
    try {
      loading.value = true
      error.value = null

      const response = await coinHistoryService.getTopupHistory({
        limit: topupPagination.value.limit,
        offset: append ? topupPagination.value.offset : 0
      })

      if (append) {
        topupHistory.value.push(...response.items)
      } else {
        topupHistory.value = response.items
      }

      topupPagination.value = {
        total: response.total,
        limit: response.limit,
        offset: response.offset
      }
    } catch (err: any) {
      error.value = err.response?.data?.error || 'Failed to load topup history'
      console.error('[useCoinHistory] Failed to load topup history:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载更多充值记录
   */
  async function loadMoreTopups() {
    if (!hasMoreTopups.value || loading.value) return
    
    topupPagination.value.offset += topupPagination.value.limit
    await loadTopupHistory(true)
  }

  /**
   * 加载消费历史
   */
  async function loadSpendingHistory(append = false) {
    try {
      loading.value = true
      error.value = null

      const response = await coinHistoryService.getSpendingHistory({
        limit: spendingPagination.value.limit,
        offset: append ? spendingPagination.value.offset : 0
      })

      if (append) {
        spendingHistory.value.push(...response.items)
      } else {
        spendingHistory.value = response.items
      }

      spendingPagination.value = {
        total: response.total,
        limit: response.limit,
        offset: response.offset
      }
    } catch (err: any) {
      error.value = err.response?.data?.error || 'Failed to load spending history'
      console.error('[useCoinHistory] Failed to load spending history:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载更多消费记录
   */
  async function loadMoreSpendings() {
    if (!hasMoreSpendings.value || loading.value) return
    
    spendingPagination.value.offset += spendingPagination.value.limit
    await loadSpendingHistory(true)
  }

  /**
   * 加载金币统计摘要
   */
  async function loadSummary() {
    try {
      loading.value = true
      error.value = null
      summary.value = await coinHistoryService.getCoinSummary()
    } catch (err: any) {
      error.value = err.response?.data?.error || 'Failed to load coin summary'
      console.error('[useCoinHistory] Failed to load summary:', err)
    } finally {
      loading.value = false
    }
  }

  return {
    // 数据
    topupHistory,
    spendingHistory,
    summary,
    loading,
    error,
    
    // 分页
    topupPagination,
    spendingPagination,
    hasMoreTopups,
    hasMoreSpendings,
    
    // 方法
    loadTopupHistory,
    loadMoreTopups,
    loadSpendingHistory,
    loadMoreSpendings,
    loadSummary
  }
}
```

#### 3. 在组件中使用

```vue
<!-- src/pages/CoinHistoryPage.vue -->
<template>
  <div class="coin-history-page">
    <!-- 金币统计摘要 -->
    <div v-if="summary" class="summary-card">
      <h2>金币统计</h2>
      <div class="summary-grid">
        <div class="summary-item">
          <span class="label">当前余额</span>
          <span class="value">{{ summary.current_balance }}</span>
        </div>
        <div class="summary-item">
          <span class="label">累计购买</span>
          <span class="value">{{ summary.total_purchased }}</span>
        </div>
        <div class="summary-item">
          <span class="label">累计赠送</span>
          <span class="value">{{ summary.total_bonus }}</span>
        </div>
        <div class="summary-item">
          <span class="label">累计消费</span>
          <span class="value">{{ summary.total_spent }}</span>
        </div>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button 
        :class="{ active: activeTab === 'topup' }"
        @click="activeTab = 'topup'"
      >
        充值历史 ({{ topupPagination.total }})
      </button>
      <button 
        :class="{ active: activeTab === 'spending' }"
        @click="activeTab = 'spending'"
      >
        消费历史 ({{ spendingPagination.total }})
      </button>
    </div>

    <!-- 充值历史 -->
    <div v-if="activeTab === 'topup'" class="history-list">
      <div v-if="loading && topupHistory.length === 0" class="loading">
        加载中...
      </div>
      
      <div v-else-if="topupHistory.length === 0" class="empty">
        暂无充值记录
      </div>
      
      <div v-else>
        <div 
          v-for="item in topupHistory" 
          :key="item.id"
          class="history-item"
        >
          <div class="item-header">
            <span class="date">{{ formatDate(item.created_at) }}</span>
            <span :class="['status', item.status]">
              {{ getStatusText(item.status) }}
            </span>
          </div>
          <div class="item-body">
            <div class="coins">
              <span class="amount">+{{ item.coins_total }}</span>
              <span class="detail">
                ({{ item.coins_purchased }} 购买
                <template v-if="item.coins_bonus > 0">
                  + {{ item.coins_bonus }} 赠送
                </template>)
              </span>
            </div>
            <div class="price">${{ item.amount_usd.toFixed(2) }}</div>
          </div>
        </div>

        <!-- 加载更多 -->
        <button 
          v-if="hasMoreTopups"
          @click="loadMoreTopups"
          :disabled="loading"
          class="load-more"
        >
          {{ loading ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </div>

    <!-- 消费历史 -->
    <div v-if="activeTab === 'spending'" class="history-list">
      <div v-if="loading && spendingHistory.length === 0" class="loading">
        加载中...
      </div>
      
      <div v-else-if="spendingHistory.length === 0" class="empty">
        暂无消费记录
      </div>
      
      <div v-else>
        <div 
          v-for="item in spendingHistory" 
          :key="item.id"
          class="history-item"
        >
          <div class="item-header">
            <span class="date">{{ formatDate(item.created_at) }}</span>
          </div>
          <div class="item-body">
            <div class="service">
              <div class="service-name">{{ item.service_name }}</div>
              <div class="service-detail">
                {{ item.service_quantity }} × {{ item.coin_unit_price }} 金币
              </div>
            </div>
            <div class="coins spent">-{{ item.coins_spent }}</div>
          </div>
        </div>

        <!-- 加载更多 -->
        <button 
          v-if="hasMoreSpendings"
          @click="loadMoreSpendings"
          :disabled="loading"
          class="load-more"
        >
          {{ loading ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useCoinHistory } from '@/composables/useCoinHistory'

const {
  topupHistory,
  spendingHistory,
  summary,
  loading,
  error,
  topupPagination,
  spendingPagination,
  hasMoreTopups,
  hasMoreSpendings,
  loadTopupHistory,
  loadMoreTopups,
  loadSpendingHistory,
  loadMoreSpendings,
  loadSummary
} = useCoinHistory()

const activeTab = ref<'topup' | 'spending'>('topup')

onMounted(async () => {
  await Promise.all([
    loadSummary(),
    loadTopupHistory(),
    loadSpendingHistory()
  ])
})

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getStatusText(status: string) {
  const statusMap: Record<string, string> = {
    pending: '处理中',
    completed: '已完成',
    expired: '已过期',
    canceled: '已取消'
  }
  return statusMap[status] || status
}
</script>

<style scoped>
/* 样式省略，根据实际设计添加 */
</style>
```

---

## React 示例

```typescript
// src/hooks/useCoinHistory.ts
import { useState, useCallback } from 'react'
import { coinHistoryService, type TopupHistoryItem, type SpendingHistoryItem, type CoinSummary } from '@/services/coinHistoryService'

export function useCoinHistory() {
  const [topupHistory, setTopupHistory] = useState<TopupHistoryItem[]>([])
  const [spendingHistory, setSpendingHistory] = useState<SpendingHistoryItem[]>([])
  const [summary, setSummary] = useState<CoinSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [topupPagination, setTopupPagination] = useState({
    total: 0,
    limit: 20,
    offset: 0
  })

  const [spendingPagination, setSpendingPagination] = useState({
    total: 0,
    limit: 20,
    offset: 0
  })

  const loadTopupHistory = useCallback(async (append = false) => {
    try {
      setLoading(true)
      setError(null)

      const response = await coinHistoryService.getTopupHistory({
        limit: topupPagination.limit,
        offset: append ? topupPagination.offset : 0
      })

      setTopupHistory(prev => append ? [...prev, ...response.items] : response.items)
      setTopupPagination({
        total: response.total,
        limit: response.limit,
        offset: response.offset
      })
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load topup history')
    } finally {
      setLoading(false)
    }
  }, [topupPagination.limit, topupPagination.offset])

  // 其他方法类似...

  return {
    topupHistory,
    spendingHistory,
    summary,
    loading,
    error,
    topupPagination,
    spendingPagination,
    loadTopupHistory,
    // ...
  }
}
```

---

## 注意事项

### 1. 认证

所有 API 都需要用户登录，确保：
- 使用 `withCredentials: true` 携带 Cookie
- 处理 401 错误，引导用户登录

### 2. 分页

- 使用 `limit` 和 `offset` 实现分页
- 建议每页 20-50 条记录
- 实现"加载更多"或分页器

### 3. 时间格式

- API 返回 ISO 8601 格式时间
- 客户端需要格式化为本地时间

### 4. 错误处理

处理常见错误：
- `401 not_authenticated` - 跳转到登录页
- `404 user_not_found` - 用户不存在
- `503 database_unavailable` - 服务暂时不可用

### 5. 性能优化

- 使用虚拟滚动处理大量数据
- 缓存已加载的数据
- 实现下拉刷新

---

## 测试

### 使用 curl 测试

```bash
# 1. 先登录获取 session cookie
# （假设已经登录）

# 2. 测试充值历史
curl -X GET 'http://localhost:5010/api/coins/topup-history?limit=5' \
  -H 'Cookie: app_session=your_session_id' \
  | jq

# 3. 测试消费历史
curl -X GET 'http://localhost:5010/api/coins/spending-history?limit=5' \
  -H 'Cookie: app_session=your_session_id' \
  | jq

# 4. 测试统计摘要
curl -X GET 'http://localhost:5010/api/coins/summary' \
  -H 'Cookie: app_session=your_session_id' \
  | jq
```

---

## 更新日志

- 2025-10-26: 初始版本，实现充值历史、消费历史和统计摘要 API
