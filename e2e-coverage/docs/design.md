# E2E Coverage — 设计文档

## 1. 概述

E2E Coverage 是一个基于 LLM Agent 的黑盒 UI 自动探索系统，用于 macOS 应用的端到端测试覆盖。系统自动发现应用的所有可交互状态和元素，构建状态转换图（UTG），并生成测试流程和可视化报告。

### 1.1 核心设计理念

**LLM 智能 + 算法完备性 = 可靠的自动探索**

纯算法爬虫缺乏语义理解能力（不知道该在输入框里填什么、不理解弹窗含义、无法判断功能边界）；纯 LLM 探索缺乏系统性（容易遗漏元素、重复点击、迷失在状态空间中）。本系统将两者结合：

- **LLM（Claude）** 负责执行：操控 UI、语义理解、智能输入、错误恢复、范围判断
- **Algorithm Advisor（Python 脚本）** 负责规划：追踪已探索/未探索元素、决定下一步目标、确保不遗漏

两者通过 JSON 接口通信，互不侵入。

### 1.2 Harness Engineering

本系统借鉴了 Anthropic 提出的 **Harness Engineering** 理念：

> "不要试图让 LLM 通过 prompt 完美遵循所有规则，而是在 LLM 外围构建代码层面的确定性约束（harness），让 LLM 专注于需要智能的部分。"

具体体现：

| 设计决策 | Harness Engineering 原则 |
|---------|------------------------|
| Advisor 算法控制探索顺序（不由 LLM 决定下一步点什么） | 减少 LLM 决策空间（Action Space） |
| Phase 0 结束后对初始状态的非目标元素逐个 skip（不做全局 label 黑名单） | 精确过滤，避免误伤深层同名元素 |
| Skip 命令强制单次 + 必须带 reason + 分离存储 | 防呆设计（Poka-yoke） |
| 独立 Evaluator sub-agent 审查探索结果 | Generator-Evaluator 分离模式 |
| `crawler_state.json` 持久化全部状态 | 结构化状态交接（Context Handoff） |

---

## 2. 背景与目标

### 2.1 问题

当前 macOS 桌面应用的 E2E 测试存在以下痛点：

- **覆盖率不可见**：团队不知道现有测试覆盖了哪些用户流程，遗漏了哪些。
- **缺少 Case 基线**：很多项目初始阶段没有完善的 E2E 用例，需要从零构建。
- **覆盖率瓶颈**：学术研究表明，现有自动化 GUI 测试工具在真实应用中活动覆盖率普遍难以超过 30%（CovAgent, 2026）。
- **状态识别粗糙**：传统工具使用 MD5 哈希做状态识别，无法处理"内容不同但语义相同"的页面。
- **缺乏全局视图**：没有一个可视化报告能直观展示"哪些用户流程已覆盖、哪些未覆盖"。

### 2.2 目标

构建一套工具，面向 **macOS 桌面应用**（如 Edge 浏览器、天气 App 等），实现：

1. **自动遍历**：通过 MCP 工具程序化遍历应用的所有页面和可交互元素，构建 UI 状态转移图（UTG）。
2. **Flow 生成**：基于状态图（知识库），由 LLM 设计有意义的测试 Flow（happy path、边界、异常）。
3. **可视化报告**：生成状态图 + Flow 表格的交互式报告。

### 2.3 目标平台

- **macOS 桌面应用**（首要）
- 操作工具：**MCP Appium Server**（通过 MCP 协议操作 macOS 应用）
- 后续扩展：iOS App、Web 应用

---

## 3. 三层模型：状态图、Flow、Case

本方案的核心是区分三个层次：

```
Layer 1: 状态图（State Graph）    ← 知识库，App 的完整地图
         节点 = 遍历发现的所有页面
         边   = 遍历发现的所有操作
         自动遍历的产物

Layer 2: Flow（测试场景）          ← 从图推导出来的测试路径
         happy path / 边界场景 / 异常场景
         由 LLM 根据状态图 + 业务语义设计
         算法产物，e2e-coverage skill 输出

Layer 3: Case（BDD Gherkin 用例）  ← 面向执行的测试设计
         Given/When/Then 自然语言步骤
         LLM 基于 Flow + ui_tree 生成
         LLM 产物，未来 bdd-gen skill 输出
```

### 3.1 三者关系

| | 状态图 | Flow | BDD Case |
|---|---|---|---|
| **本质** | 知识库（App 能做什么） | 图上路径覆盖（算法产物） | 面向用户场景的测试设计（LLM 产物） |
| **粒度** | 单步操作（A→B） | 端到端路径（A→B→C→D→E） | Given/When/Then 自然语言步骤 |
| **需要的数据** | page_source XML | utg.json（图拓扑） | flows.json + states/s_xxx.json（需要 ui_tree） |
| **归属** | e2e-coverage skill (Phase 1) | e2e-coverage skill (Phase 2) | 独立的 bdd-gen skill |

### 3.2 为什么分成两个 Skill

Flow 是 e2e-coverage 的自然产出（基于状态图拓扑设计路径覆盖），而 BDD Case 是下游消费者（需要 ui_tree 的层级上下文来写精确的 Gherkin step）。两者的输入数据、生成逻辑、使用场景不同，分离后各自职责清晰，也允许独立迭代。

### 3.3 关键区别：状态图 vs Flow

| | 状态图 | Flow |
|---|---|---|
| 状态上下文 | 每步可能从任意状态跳入 | 必须按序执行，状态有前后依赖 |
| 覆盖的含义 | 边被"触达过"不等于被"验证过" | Flow 通过 = 场景被完整验证 |
| 数量 | 遍历完即固定 | 路径组合，远多于边的数量 |

---

## 4. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Code Session                   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              e2e-coverage Skill Prompt             │   │
│  │         (e2e-coverage.md, 探索协议定义)             │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                    │
│  ┌──────────────────▼───────────────────────────────┐   │
│  │            Explorer Agent (Main LLM)              │   │
│  │                                                   │   │
│  │  ┌─────────┐  ┌───────────┐  ┌───────────────┐  │   │
│  │  │ MCP     │  │ Advisor   │  │ File I/O      │  │   │
│  │  │ Appium  │  │ CLI Call  │  │ (page_source,  │  │   │
│  │  │ Tools   │  │ (Bash)    │  │  screenshots)  │  │   │
│  │  └────┬────┘  └─────┬─────┘  └───────┬───────┘  │   │
│  └───────┼─────────────┼────────────────┼───────────┘   │
│          │             │                │                │
│  ┌───────▼─────┐ ┌─────▼──────┐ ┌──────▼───────┐       │
│  │  Appium     │ │  advisor.py │ │  e2e_output/  │       │
│  │  Server     │ │  normalize  │ │  (持久化状态)  │       │
│  │  (4723)     │ │  .py        │ │              │       │
│  └─────────────┘ └────────────┘ └──────────────┘       │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Evaluator Sub-agent (Phase 1.5)           │   │
│  │         独立 context, 审查 crawler_state.json      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 4.1 组件职责

| 组件 | 类型 | 职责 |
|------|------|------|
| **e2e-coverage.md** | Skill Prompt | 定义探索协议、各 Phase 的执行步骤、LLM 行为约束 |
| **Explorer Agent** | LLM (Claude) | 操控 UI、执行点击/输入、语义判断（scope、state naming）、错误恢复 |
| **advisor.py** | Python 脚本 | 状态管理、未探索元素计算、Chrome 自动过滤、探索进度追踪 |
| **normalize.py** | Python 脚本 | 解析 Appium XML、提取可交互元素、计算状态指纹（hash）、构建 ui_tree |
| **Evaluator Sub-agent** | LLM (Claude) | 独立 context，审查 Explorer 的 skip 决定，发现遗漏 |
| **report.py** | Python 脚本 | 读取 UTG + flows，生成交互式 HTML 报告 |
| **MCP Appium Server** | MCP Server | 提供 app_launch、click_element、get_page_source_tree 等工具 |

---

## 5. 执行流程

### Phase 0: Feature Scoping — LLM 导航到目标功能

```
用户指定: "Edge Favorites 功能"
        │
        ▼
LLM 启动 app → 获取初始 page_source
        │
        ▼
LLM 分析 XML → 识别入口元素（如 "Favorites" 菜单）
        │
        ▼
LLM 点击入口 → 到达目标功能的主界面
        │
        ▼
advisor init → 以目标功能主界面为 s0
        │
        ▼
LLM 对 s0 上非目标入口的元素逐个 advisor skip
  （如 "Back"、"Address bar"、"Settings and more" 等）
  每个 skip 带 reason: "not target entry — browser navigation"
写入 exploration_context.txt（功能范围定义，供 Evaluator 使用）
```

**设计意图**: Phase 0 的非目标元素过滤通过现有的 `skip` 命令完成，精确到 `(s0, element_key)` 对。不使用全局 label 黑名单，避免误伤深层状态中同名但属于目标功能的元素。

### Phase 1: Explore — LLM 执行 + 算法规划

```
┌─────────────────────────────────────────┐
│            Exploration Loop              │
│                                         │
│  ┌─────────────────────────────┐        │
│  │  advisor next               │        │
│  │  → 返回: target_state +     │        │
│  │    elements (按优先级排序)    │        │
│  └──────────┬──────────────────┘        │
│             │                           │
│  ┌──────────▼──────────────────┐        │
│  │  LLM 导航到 target_state    │        │
│  │  (Escape / 重启 app /       │        │
│  │   按 navigate_path 回放)    │        │
│  └──────────┬──────────────────┘        │
│             │                           │
│  ┌──────────▼──────────────────┐        │
│  │  对每个 element:             │        │
│  │  1. LLM 执行 CLICK/TYPE     │        │
│  │  2. 保存新 page_source      │        │
│  │  3. advisor record           │        │
│  │  4. 处理结果:                │        │
│  │     - new_state → 截图 +    │        │
│  │       scope 判断             │        │
│  │     - known_state → 记录    │        │
│  │     - same_state → 记录     │        │
│  │  5. 恢复到 target_state     │        │
│  └──────────┬──────────────────┘        │
│             │                           │
│  ┌──────────▼──────────────────┐        │
│  │  advisor 返回 status: done? │        │
│  │  否 → 回到 advisor next     │        │
│  │  是 → 进入 Phase 1.5        │        │
│  └─────────────────────────────┘        │
└─────────────────────────────────────────┘
```

#### 5.1 Advisor 算法

Advisor 是无状态的 CLI 工具，每次被调用时读取 `crawler_state.json`，计算后返回结果。

**核心数据结构（三元组格式）：**

```json
{
  "state_index": ["s_ae71357b", "s_3be66661"],
  "transitions": [
    {"from": "s_ae71357b", "to": "s_3be66661", "action": "CLICK(More options)"}
  ],
  "explored_pairs": [
    ["s_ae71357b", "More options", "CLICK"],
    ["s_ae71357b", "More options", "RIGHT_CLICK"]
  ],
  "skipped_pairs": [
    ["s_ae71357b", "NTP Link", "CLICK", "out of scope"]
  ],
  "queue": ["s_3be66661"],
  "path_from_s0": {"s_3be66661": [{"action": "CLICK(More options)", "label": "More options", "from_state": "s_ae71357b"}]}
}
```

> `explored_pairs` 和 `skipped_pairs` 使用三元组 `(state_id, effective_key, action_type)`，同一个元素的不同动作类型（CLICK、TYPE、RIGHT_CLICK、DRAG）独立追踪。每个 state 的元素列表和 ui_tree 存储在独立的 `states/s_xxx.json` 中。

**`next` 命令的选择策略：**

1. 遍历 `queue` 中的所有状态
2. 计算每个状态的未探索 `(element, action_type)` 条目数
3. 选择**未探索条目最多**的状态（贪心策略）
4. 返回该状态的所有未探索条目，按优先级排序：CLICK/TYPE → RIGHT_CLICK → DRAG

**探索终止条件（三选一）：**

- 所有可达状态的所有元素都已探索
- 达到 `max_actions` 限制
- 达到 `max_states` 限制

**Advisor CLI 命令：**

| 命令 | 用途 | 调用者 |
|------|------|--------|
| `init` | 初始化探索状态 | Explorer Agent |
| `next` | 返回下一批待探索元素 | Explorer Agent |
| `record` | 记录一次操作的结果（含 `--action-type`） | Explorer Agent |
| `skip` | 标记单个元素的某个动作为 skipped（带 reason + action-type，分离存储） | Explorer Agent |
| `unskip` | 移除 skipped 标记，重新加入待探索 | Evaluator Sub-agent |
| `restore-failure` | 记录状态恢复失败 | Explorer Agent |
| `status` | 返回探索进度摘要 | Explorer Agent |
| `finalize` | 生成 utg.json | Explorer Agent |

#### 5.2 LLM 承担的语义任务

| 任务 | 为什么必须由 LLM 做 |
|------|-------------------|
| Smart text input | 需要根据输入框语义生成合理的文本（email 字段填 email 格式） |
| Scope 判断 | 算法不理解"Copilot 功能"的边界，只有 LLM 能判断新状态是否属于目标功能 |
| State naming | 给状态取描述性名称（"Settings Panel" 而非 "s_abc123"），需要理解 UI 内容 |
| Error recovery | MCP 操作失败时需要智能重试（换不同的点击策略、处理意外弹窗） |
| 恢复导航 | 当前状态偏离 target_state 时，需要智能恢复（尝试 Escape、重启 app、回放路径） |
| DRAG 目标选择 | 算法不知道拖拽到哪里有意义——拖到同级元素（排序）还是不同容器（移动），需要 LLM 根据 UI 语义判断 |

### Phase 1.5: Validate — Sub-agent Evaluator 审查

```
Explorer Agent 完成探索
        │
        ▼
启动 Evaluator Sub-agent（独立 context window）
        │
        ├── 读取 exploration_context.txt（功能范围）
        ├── 读取 crawler_state.json（探索状态）
        │
        ▼ 审查:
        │  - skipped_pairs 中每个 skip 的 reason 是否合理
        │  - 是否有状态被发现但从未被探索（0 outgoing transitions）
        │
        ▼ 输出:
        │  verdict: "pass" → 进入 Phase 2
        │  verdict: "re-explore" → unskip 错误的 skip，重跑 Phase 1 补漏
        │
        ▼ 如果需要补漏，循环直到 verdict: "pass"
```

### Phase 2: Design Flows — LLM 设计测试流程

```
读取 utg.json（状态转换图）
        │
        ▼
LLM 设计测试流程，覆盖所有 transition edge
        │
        ├── happy: 核心用户旅程
        ├── error: 异常/无效操作
        └── boundary: 边界情况
        │
        ▼
输出 flows.json
```

### Phase 3: Generate Report — 脚本生成报告

```
report.py 读取 utg.json + flows.json
        │
        ▼
输出 report.html（交互式状态图 + 截图 + 测试流程）
```

---

## 6. 数据流与持久化

```
                   ┌──────────────┐
                   │  MCP Appium  │
                   └───────┬──────┘
                           │ page_source XML
                   ┌───────▼──────┐
                   │ normalize.py │
                   └───────┬──────┘
                           │ state_id, hash, interactive_elements, ui_tree
                   ┌───────▼──────┐
                   │  advisor.py  │
                   └───────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  crawler_state.json  states/s_xxx.json  states/s_xxx.png
  (探索进度，轻量)    (元素+ui_tree)     (每状态截图)
         │
         ▼
  utg.json (状态图摘要)  →  report.py  →  report.html
```

### 6.1 文件结构

```
e2e_output/
├── states/
│   ├── s_ae71357b.png          # 截图
│   ├── s_ae71357b.json         # 单个 state 详情（元素列表 + UI 树）
│   ├── s_3be66661.png
│   ├── s_3be66661.json
│   └── ...
├── exploration_context.txt     # 功能范围定义（Phase 0）
├── crawler_state.json          # 探索进度（轻量，不含元素详情）
├── utg.json                    # 状态图摘要（轻量，引用 state 文件）
├── flows.json                  # 测试流
└── report.html                 # 报告
```

### 6.2 关键文件格式

**`states/s_xxx.json`** — 单个状态详情：

```json
{
  "state_id": "s_ae71357b",
  "state_hash": "ae71357b1234",
  "window_title": "Favorites Panel",
  "screenshot": "states/s_ae71357b.png",
  "interactive_elements": [
    {"type": "XCUIElementTypeButton", "label": "More options", "x": 1356, "y": 115, "width": 28, "height": 29},
    {"type": "XCUIElementTypeButton", "label": "Add this page to favorites (⌘D)", "x": 100, "y": 115, "width": 28, "height": 29, "shortcut": "⌘D"}
  ],
  "shortcuts": [
    {"shortcut": "⌘D", "label": "Add this page to favorites", "type": "XCUIElementTypeButton"}
  ],
  "ui_tree": {
    "tag": "Window", "title": "Favorites",
    "children": [
      {
        "tag": "Toolbar", "label": "Favorites toolbar",
        "children": [
          {"tag": "Button", "label": "Search favorites"},
          {"tag": "Button", "label": "More options"}
        ]
      }
    ]
  }
}
```

**`crawler_state.json`** — 探索进度（轻量，不内嵌元素详情）：

```json
{
  "app_name": "Edge",
  "start_time": 1713100000,
  "start_state": "s_ae71357b",
  "state_index": ["s_ae71357b", "s_3be66661"],
  "transitions": [...],
  "explored_pairs": [...],
  "skipped_pairs": [...],
  "path_from_s0": {...},
  "queue": ["s_3be66661"],
  "action_count": 5
}
```

**`utg.json`** — 状态图摘要（轻量）：

```json
{
  "app_name": "Edge",
  "start_state": "s_ae71357b",
  "states": {
    "s_ae71357b": {
      "window_title": "Favorites Panel",
      "interactive_elements_count": 50,
      "screenshot": "states/s_ae71357b.png"
    }
  },
  "transitions": [...],
  "edges": [["s_ae71357b", "s_3be66661"]],
  "shortcuts": [
    {"shortcut": "⌘D", "label": "Add this page to favorites", "type": "XCUIElementTypeButton", "source_state": "s_ae71357b"}
  ],
  "stats": {"total_states": 2, "total_transitions": 1, "elapsed_seconds": 120}
}
```

### 6.3 各消费者读什么

| 消费者 | 读取文件 |
|--------|---------|
| advisor（探索中） | `crawler_state.json` + `states/s_xxx.json`（按需读元素列表） |
| report.py | `utg.json`（轻量）+ `flows.json` |
| Flow 设计（Claude） | `utg.json`（图拓扑 + 标题） |
| bdd-gen（未来） | `flows.json` + `states/s_xxx.json`（需要 ui_tree 写 Gherkin step） |

### 6.4 断点恢复

`crawler_state.json` 保存了完整的探索进度。如果探索中断（context 溢出、session 终止），下次启动时：

1. `advisor status` 检测到已有状态 → 返回进度摘要
2. LLM 直接从探索循环继续，无需重新初始化

---

## 7. 状态指纹设计

### 7.1 当前方案

```
page_source XML
    │
    ▼ 解析所有 XCUI 元素
    │
    ▼ 提取 label（优先级: label > name > title）
    │   使用 or 短路: attrs.get("label") or attrs.get("name") or attrs.get("title") or ""
    │   确保 label="" 时能 fallback 到 title 属性
    │
    ▼ 过滤出可交互元素
    │   条件: 在 INTERACTIVE_TYPES 中 + enabled + visible + label 不在 SKIP_LABELS 中
    │         + y > 50 (排除菜单栏) + width/height > 0
    │
    ▼ 计算 state_hash
    │   MD5( sorted( "type|label|enabled" for each element ) )[:12]
    │
    ▼ 生成 state_id: "s_" + state_hash[:8]
```

**相同状态** = 相同的可交互元素集合（不关心位置变化，只关心类型+标签+状态）。

- 不含坐标 → 窗口拖动/缩放不影响 hash
- 不含 selected/checked → 避免状态爆炸（见 §10）

### 7.2 参考 DroidBot

DroidBot (Android) 用: `class + resource_id + text(截断50字符) + enabled + checked + selected`。
我们的方案与 DroidBot 等价，差异是 macOS 没有 resource_id（用 label 替代）、不用 selected（有意简化）。

### 7.3 已知局限

- label 受本地化语言影响 → 切换系统语言后断点续传会失效
- 8 位 hex 碰撞概率极低（~4 亿分之一），实际场景不可能撞

---

## 8. UI 树 (ui_tree)

### 8.1 用途

为下游 BDD case 生成和脚本生成提供元素的层级上下文。

- **没有 ui_tree**: `When I click "More options"` — 页面上可能有多个 More options
- **有 ui_tree**: `When I click the "More options" button in the Favorites toolbar` — 精确定位

### 8.2 生成规则

从原始 page_source XML 构建精简树：

1. 去掉坐标、enabled、visible、value 等属性
2. 去掉 `y <= 50` 的菜单栏区域节点
3. 折叠无意义的中间容器：连续嵌套的无 label 无 title 的 Group 合并
4. 只保留有 label/title 的节点、包含交互元素的容器、交互元素本身
5. tag 名简化：`XCUIElementTypeButton` → `Button`

---

## 9. Harness 可靠性设计

### 9.1 解决的核心问题

LLM Agent 在长时间运行中面临的可靠性挑战：

| 挑战 | 表现 | 本系统的应对 |
|------|------|------------|
| **指令遵循衰减** | Context 越长，LLM 越容易偏离协议规则 | 把关键约束放到代码（advisor）里，不依赖 LLM 记住规则 |
| **批量错误** | LLM 一次错误决策影响大量元素 | `skip` 改为单次操作 + 强制带 reason，限制爆炸半径 |
| **自评偏见** | LLM 不擅长否定自己的工作 | 独立的 Evaluator sub-agent，fresh context，无历史偏见 |
| **不可逆操作** | 元素被 skip 后无法恢复 | `skipped_pairs` 与 `explored_pairs` 分离存储，支持审计和回滚 |

### 9.2 Skip 机制演进

Skip 是整个系统中最容易出错的操作——它把一个语义判断（"这个元素是否在 scope 内"）转化为一个不可逆操作（"标记为已探索"）。

**V1 设计（有缺陷）：**

```bash
# 批量 skip，无 reason，直接写入 explored_pairs
advisor.py skip --state s_xxx --effective-keys key1 key2 key3 ... key39
```

问题：一次调用跳过 39 个元素，无审计痕迹，无法恢复。

**V2 设计（当前）：**

```bash
# 单次 skip，必须带 reason，存入独立的 skipped_pairs
advisor.py skip --state s_xxx --effective-key key1 --reason "NTP element, out of Copilot scope"
```

改进：
- **单次操作** — 每次只 skip 一个元素，降低批量错误的影响
- **强制 reason** — LLM 必须给出理由，增加决策成本，减少草率 skip
- **分离存储** — `skipped_pairs` 独立于 `explored_pairs`，支持后续审计
- **可恢复** — Evaluator 审查后可以通过 `unskip` 命令移除，重新探索

### 9.3 多 Agent 协作

```
Explorer Agent                    Evaluator Sub-agent
(长 context, 可能有偏见)           (fresh context, 无偏见)
     │                                   │
     │  执行探索，产出                     │
     │  crawler_state.json               │
     │  (含 skipped_pairs)               │
     │                                   │
     │──────── 文件传递 ─────────────────▶│
     │                                   │
     │                            读取 crawler_state.json
     │                            读取 exploration_context.txt
     │                            审查每个 skip 的 reason
     │                            检查未探索的状态
     │                                   │
     │◀──────── JSON 结果 ───────────────│
     │                                   │
     │  根据 verdict 决定:
     │  - pass → Phase 2
     │  - re-explore → unskip 错误 skip，
     │    重跑 Phase 1 补漏
```

**通信方式**: 文件（`crawler_state.json`），不是对话。这是 harness engineering 的关键——Agent 之间通过结构化数据交换信息，由协议（skill prompt）控制流程，而不是让任何一个 Agent 主导编排。

**为什么用独立的 Sub-agent 而不是脚本检查或 Explorer 自检：**

| 方案 | 可靠性 | 原因 |
|------|--------|------|
| 脚本检查 | 低 | 只能检查结构异常（如 0 transitions），无法判断 skip reason 是否合理——这是语义判断 |
| Explorer 自检 | 低 | Anthropic 研究表明 "agents asked to evaluate their own work tend to confidently praise the work"——自评偏见 |
| **独立 Sub-agent** | **高** | 全新 context window（无探索历史偏见）+ 被 prompt 为严格的 QA 审查者 |

---

## 10. 设计探索与演进

本节记录关键设计决策的 why，供后续维护者理解上下文。

### 10.1 为什么选 LLM + Advisor 而非纯 Python 爬虫

最初方案（design-doc.md Phase 1）是纯代码遍历，类 DroidBot 方式。实际尝试后发现：

- macOS 应用的 UI 交互比 Android 更复杂（弹出菜单、多窗口、悬浮面板）
- 纯算法不知道在输入框里填什么、不理解弹窗含义、无法判断功能边界
- 但纯 LLM 探索又缺乏系统性，容易遗漏元素

最终选择 LLM 做执行（需要语义理解的部分）+ 算法做规划（需要系统性的部分），两者通过 JSON 接口通信。

### 10.2 为什么 skip 从批量改为单次 + reason

实际运行中发现：Explorer Agent 在长 context 中发现新状态后，会用 `skip --effective-keys key1 key2 ... key39` 批量跳过所有元素。Copilot Attach Files Menu（39 元素）、Copilot Mode Selector（35 元素）等状态被完全跳过。

根因分析：
1. 批量操作 → 单次错误影响面大
2. 无 reason → 无审计痕迹
3. "不要 skip"是否定指令，LLM 在长 context 中遵循度低
4. skipped 和 explored 混合存储 → 事后无法区分和恢复

改为单次 + 强制 reason + 分离存储后，错误影响面从 N 降到 1，且支持 Evaluator 审查和 unskip。

### 10.3 为什么引入 Evaluator Sub-agent

Anthropic 研究发现 "agents asked to evaluate their own work tend to confidently praise the work"。让 Explorer 自己审查 skip 决定不可靠。

独立 Sub-agent 的优势：全新 context window（无探索过程中积累的偏见），被 prompt 为严格的 QA 审查者角色。通信通过文件（crawler_state.json）而非对话，确保结构化交接。

### 10.4 为什么去掉 chrome_labels.txt 全局黑名单

早期设计在 Phase 0 捕获初始页面所有元素 label 存入 `chrome_labels.txt`，advisor 在所有 state 中按 label 文本匹配自动 skip。两个问题：

1. **探索目标可能就是 app 本身的功能**（如探索 Edge Favorites），所以"Chrome 元素"这个概念不成立
2. **纯 label 匹配跨 state 误伤**：菜单栏的 "Favorites" 和 Favorites 面板内同名元素会被一起过滤

改为 Phase 0 结束后对初始状态（s0）的非目标元素逐个 `skip`，精确到 `(s0, element_key)` 对。复用现有 skip 机制，不需要独立文件和过滤逻辑。

### 10.5 为什么引入 RIGHT_CLICK 和 DRAG 动作类型

早期只有 CLICK 和 TYPE 两种动作，explored_pairs 是二元组 `(state_id, element_key)`。实际探索中发现很多功能隐藏在右键菜单里（如收藏夹的重命名、删除），列表类元素还支持拖拽排序。

引入 RIGHT_CLICK 和 DRAG 后，explored_pairs 扩展为三元组 `(state_id, element_key, action_type)`，同一个元素的不同动作独立追踪。normalize.py 根据元素类型给出 `eligible_actions`（偏宽松），advisor 按优先级（CLICK → RIGHT_CLICK → DRAG）排序返回。DRAG 的目标选择交给 LLM 的语义理解——拖到同级元素（排序）还是不同容器（移动），算法无法判断。

### 10.7 快捷键信息为什么被动采集而非主动探索

macOS 菜单栏的菜单项（含快捷键）只有展开菜单后才出现在 accessibility tree 中，且菜单栏在 `y <= 50` 区域被 normalize.py 过滤。主动遍历菜单栏来采集快捷键代价高且偏离主流程。

实际观察发现，很多快捷键信息已经嵌在按钮 label 中（如 `"Add this page to favorites (⌘D)"`）。因此采用被动策略：normalize.py 在解析元素时用正则提取 label 中的快捷键模式，存入 state detail 和 utg.json。Flow 设计时 LLM 可以据此标注 `shortcut_alternative`，下游 bdd-gen 生成快捷键版测试用例。

### 10.8 状态指纹为什么不含 selected/checked

DroidBot 的指纹包含 `checked + selected`，但我们有意去掉。原因：macOS 应用中大量元素有 selected 状态（如 tab 切换、列表选中），如果纳入指纹，同一个面板仅因选中项不同就会产生大量不同 state_id，导致状态爆炸。权衡后选择不含 selected/checked，以牺牲少量精度换取状态空间的可控性。

---

## 11. 参考

- **DroidBot** (Li et al., ICSE-C 2017) — Android 轻量级 UI 测试输入生成器，使用 UTG（UI Transition Graph）+ BFS/DFS 遍历。本系统的状态图和 Advisor 算法直接借鉴其设计。
- **DroidBot-GPT** (Wen et al., 2023) — 在 DroidBot 基础上引入 GPT 做动作选择，但状态识别仍为 MD5 哈希未改造。启发了我们"LLM 做执行、算法做规划"的分工。
- **DroidAgent** (Kim et al., KAIST, 2024) — 引入空间记忆和规划能力，但同样未改造状态识别。
- **CovAgent** (2026, arXiv:2601.21253) — 首次提出"30% 覆盖率瓶颈"问题，使用源码分析+策略引导突破。启发了我们对覆盖率度量的思考。
- **Fastbot2** (Cai et al., ByteDance, ASE 2022) — 基于概率模型和 RL 的 Android GUI 测试，工业级实践。
- **AppAgent** (Zhang et al., Tencent, 2023) — 知识库+任务执行模式，LLM 驱动。
- **LLMDroid** (2025) — LLM 引导探索增强覆盖率。
- **EpiDroid** (2026) — 状态依赖图分析，引导测试。
- **HybridDroidbot** (2026, arXiv:2604.06763) — LLM 辅助逃出 UI 陷阱（tarpit），改善随机测试效果。
- **Crawljax** (Mesbah et al., TWEB 2012) — Ajax Web 应用的动态分析和状态变化检测，Web 领域的经典工作。
