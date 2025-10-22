# PageLikeModal 组件文档项目

## 项目概述

本项目为 PageLikeModal 及其所有下级组件创建了完整的技术文档，包括组件、Composables 等共 14 个文件的详细说明文档。

## 文档结构

### 1. 主组件
- [PageLikeModal.md](../../../src/components/pageLike/PageLikeModal.md) - 主模态框组件

### 2. Header 相关
- [ModalHeader.md](../../../src/components/header/ModalHeader.md) - 模态框头部组件

### 3. 标题组件
- [IconTabsTitle.md](../../../src/components/modalTitle/IconTabsTitle.md) - 图标 Tab 标题
- [TextTabsTitle.md](../../../src/components/modalTitle/TextTabsTitle.md) - 文本 Tab 标题
- [SimpleTitle.md](../../../src/components/modalTitle/SimpleTitle.md) - 简单标题

### 4. 手势组件
- [ModalSwipeGesture.md](../../../src/components/gesture/ModalSwipeGesture.md) - 模态框滑动手势
- [TabSwipeGesture.md](../../../src/components/gesture/TabSwipeGesture.md) - Tab 滑动手势

### 5. 按钮组件
- [ReturnButton.md](../../../src/components/backButton/ReturnButton.md) - 返回按钮
- [DownButton.md](../../../src/components/backButton/DownButton.md) - 向下按钮
- [CloseButton.md](../../../src/components/backButton/CloseButton.md) - 关闭按钮

### 6. Composables
- [useModalState.md](../../../src/components/pageLike/composables/useModalState.md) - 状态管理
- [useModalMode.md](../../../src/components/pageLike/composables/useModalMode.md) - 模式管理
- [useTabManagement.md](../../../src/components/pageLike/composables/useTabManagement.md) - Tab 管理
- [useModalGestures.md](../../../src/components/pageLike/composables/useModalGestures.md) - 手势管理
- [useModalAnimation.md](../../../src/components/pageLike/composables/useModalAnimation.md) - 动画管理

## 文档特点

### 完整性
- 涵盖所有组件和 Composables
- 包含 Props、Events、Slots 定义
- 提供使用示例和注意事项

### 实用性
- 详细的特殊逻辑说明
- 代码示例清晰易懂
- 注意事项帮助避坑

### 结构化
- 统一的文档格式
- 清晰的章节划分
- 便于查找和阅读

## 使用指南

### 查找组件文档
1. 根据组件类型找到对应分类
2. 点击文档链接查看详细说明
3. 参考使用示例进行开发

### 理解特殊逻辑
1. 阅读"特殊逻辑"章节
2. 查看代码示例
3. 注意"注意事项"部分

### 组件关系
- 每个文档都包含"相关组件"章节
- 帮助理解组件之间的依赖关系
- 便于整体架构理解

## 核心概念

### 模态框模式
- **垂直模式 (V)**: 从底部向上滑入，向下滑动关闭
- **水平模式 (H)**: 从右侧向左滑入，向右滑动关闭
- **X 模式**: 禁用滑动关闭，只能通过按钮关闭

### 手势系统
- 智能方向锁定
- 排除选择器配置
- 手势冲突处理

### Tab 管理
- 持久化支持
- 自动恢复上次选择
- 滑动切换

### 层级管理
- 自动 z-index 计算
- 模态框堆栈管理
- 多层模态框支持

## 技术栈

- Vue 3 Composition API
- TypeScript
- Ionic Framework
- Ionicons

## 维护建议

### 文档更新
- 组件修改时同步更新文档
- 保持文档与代码一致
- 添加新功能时补充说明

### 版本记录
- 在"更新日志"章节记录变更
- 标注重要的 breaking changes
- 保持版本历史清晰

## 项目统计

- 总文档数：14 个
- 组件文档：9 个
- Composable 文档：5 个
- 完成时间：2025-01-17
- 总耗时：约 1 小时

## 贡献者

- Kiro AI Assistant

## 许可证

与项目主代码库保持一致
