# Metadata Field Translate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 影片编辑页对 8 个文本字段提供同步 LLM 翻译按钮, 译文写入表单后经保存落库.

**Architecture:** `POST /api/llm/translate` 复用 `AppRuntime.translator` + `TranslationCache`; `PartialMetadata` 标 `x-translate`; SchemaForm 经 context 注入 `onTranslate`; TextField/SimpleArrayField 渲染翻译按钮.

**Tech Stack:** FastAPI · LLMTranslator · React SchemaForm · hey-api client · i18next

## Global Constraints

- 用语遵守 `docs/dev/writing.md`; 禁止中文直角引号
- 按钮 zh-CN 文案必须是 `翻译`
- 不入任务队列; 不从 `raw` 取源文; 不改刮削默认 `translate_fields`
- 测试表测试优先; 禁止玩具测试; `just generate` 后改前端
- 细粒度提交; 改文档只写现行约定

---

### Task 1: Translator 提示词 + Runtime 暴露 translator

**Files:**
- Modify: `src/amane/llm/translator.py` (`_FIELD_HINT`)
- Modify: `src/amane/app/runtime.py` (AppRuntime + build/rebuild)
- Modify: `src/amane/app/bootstrap.py` (若启动时需写入 runtime.translator)
- Test: `tests/llm/test_translator.py` (可选: 提示词存在性不必测; 既有测试仍绿)

**Interfaces:**
- Produces: `AppRuntime.translator: Translator | None` (rebuild 时更新)

- [ ] **Step 1:** 扩展 `_FIELD_HINT` 覆盖 ACTORS/DIRECTORS/TAGS/SERIES/STUDIO/PUBLISHER
- [ ] **Step 2:** `build_handlers` 返回 handlers 时同步把 translator 挂到调用方可写回的路径; `AppRuntime` 增加 `translator` 字段, `rebuild`/bootstrap 赋值
- [ ] **Step 3:** `uv run pytest tests/llm/test_translator.py -q` 通过
- [ ] **Step 4:** Commit

### Task 2: Translate API + schema x-translate + 测试

**Files:**
- Create: `src/amane/api/models/llm.py`
- Create: `src/amane/api/routes/llm.py`
- Modify: `src/amane/api/routes/__init__.py`
- Modify: `src/amane/api/models/metadata.py` (PartialMetadata extras)
- Modify: `src/amane/api/models/__init__.py` (若需导出)
- Create: `tests/api/test_llm.py`
- Modify: `docs/dev/llm.md`, `docs/dev/api.md`

**Interfaces:**
- Consumes: `runtime.translator`, `config.hot.scraping.field_language`
- Produces: `POST /api/llm/translate`

Request/response:

```python
class TranslateRequest(BaseModel):
    field: Literal["title","plot","actors","directors","tags","series","studio","publisher"]
    text: str | None = None
    texts: list[str] | None = None
    # model_validator: 恰好一个非空 (texts 允许空列表? 空列表 → 422)

class TranslateResponse(BaseModel):
    text: str | None = None
    texts: list[str] | None = None
```

- [ ] **Step 1:** 写 `tests/api/test_llm.py` 表测试 (503 无 translator; 422 缺目标语/互斥; 标量成功; 列表单项失败回填原文; 缓存命中). 用 mock translator 挂到 `app.state.runtime.translator`
- [ ] **Step 2:** 实现 models + route + 注册; PartialMetadata 八字段 `anyof_extras({"x-translate": True})`
- [ ] **Step 3:** `uv run pytest tests/api/test_llm.py -q` 通过
- [ ] **Step 4:** 更新 `docs/dev/llm.md` / `api.md`
- [ ] **Step 5:** Commit

### Task 3: OpenAPI generate + SchemaForm 翻译按钮

**Files:**
- Run: `just generate`
- Modify: `web/src/components/schema-form/schema/types.ts`
- Modify: `web/src/components/schema-form/schema-form.tsx` (context + prop)
- Modify: `web/src/components/schema-form/fields/text-field.tsx`
- Modify: `web/src/components/schema-form/fields/simple-array-field.tsx`
- Modify: `web/src/routes/meta.$metadataId.tsx`
- Modify: `web/src/i18n/locales/zh-CN/common.json`, `en/common.json`
- Modify: `docs/dev/frontend.md`

**Interfaces:**
- Consumes: generated `translateLlm` (或 OpenAPI operationId 实名)
- Produces: `onTranslate` prop / context

- [ ] **Step 1:** `just generate`
- [ ] **Step 2:** 加 `x-translate` 类型; SchemaForm context; TextField/SimpleArrayField 按钮逻辑; i18n `actions.translate`
- [ ] **Step 3:** meta 编辑弹窗接线 `onTranslate` + notifications 错误
- [ ] **Step 4:** `just fix` / web typecheck 相关检查
- [ ] **Step 5:** 更新 frontend.md; Commit

### Task 4: 验收

- [ ] **Step 1:** `uv run pytest tests/api/test_llm.py tests/llm/test_translator.py -q`
- [ ] **Step 2:** 若可行启动 `just dev`, HTTP 探测后手工或脚本点翻译路径 smoke
- [ ] **Step 3:** 确认工作区干净或仅余无关文件
