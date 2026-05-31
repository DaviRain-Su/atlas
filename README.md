# Atlas

> 类型感知(genre-aware)的深度拆书引擎:把一本硬书拆成可以被**正确学习**的知识结构,再据此生成交互式学习体验。

**护城河在拆解的深度与正确性,不在输出形态。** "做成网站"是最后一层、也是最不构成壁垒的一层。

---

## 这是什么

不是"又一个 PDF→课程"的换皮工具。Atlas 按**知识架构类型**用不同范式深拆一本书,抽出的每个知识节点都**可回溯到原文**(防幻觉),再据此生成沿依赖图导航、嵌入主动回忆的学习体验。

**v1 只攻演绎型**(数学/定理 DAG)——结构最干净、防幻觉最可落地。第一本书:Boyd & Vandenberghe《Convex Optimization》。

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | 产品需求(Why / 用户 / 竞品 / 范围 / 指标) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 技术架构与栈、演绎型数据模型(含 DDL)、五阶段流水线、MVP 切片 |

## 架构一览

```
摄入 Ingest  →  拆解引擎 Engine(护城河)  →  数据模型(typed DAG)  →  输出层 Web
 PyMuPDF        Claude 多代理抽取 + 校验          Postgres + pgvector      Next.js + React Flow
 Marker/Nougat  (Opus/Haiku, citations,                                   FastAPI · KaTeX
 (→LaTeX)        prompt caching)
```

工程量分配:**引擎 + 校验 + 评测 ≫ 数据模型 ≫ 网站**。

## 仓库结构(规划)

```
engine/   # Python:ingest / classify / extract / verify / graph / modality / schemas
api/      # FastAPI:图 + 学习者模型接口
web/      # Next.js:图 UI + 节点学习 + 主动回忆
db/       # Postgres 迁移
evals/    # gold set + 抽取质量 / 源文可回溯率评测台
docs/     # PRD.md / ARCHITECTURE.md
```

## 状态

概念已收敛,架构设计稿就绪(`docs/ARCHITECTURE.md`)。下一步:对第一本书跑摄入 spike,验证公式还原率与 span 保真度。
