# 影片编辑字段即时翻译

## 背景

刮削管线在 LLM token 耗尽时会机会主义降级, 标题等字段可能以源语言落库.
重新刮削会重复下载剧照与封面. 需要在影片详情编辑页对指定文本字段单独触发翻译,
不经任务队列, 译文写入表单后经既有 dirty / 保存条确认再落库.

## 目标

- 编辑页对 title / actors / studio / publisher / tags / series / plot / directors 提供翻译按钮
- 可空标量原 Clear 改为翻译按钮; 字符串数组在有内容时显示翻译按钮
- 按钮文案: zh-CN 为 `翻译`, en 为 `Translate`
- 源文为当前表单值; 列表字段逐项翻译
- 同步 HTTP 调用 LLM, 不入任务队列; 不写库直至用户保存

## 非目标

- 一键翻译全部字段
- 详情只读页、演员编辑页的翻译入口
- 修改刮削管线默认 `llm.translate_fields` (仍仅 title/plot)
- 强制绕过译文缓存的 UI 开关
- 从 `Metadata.raw` 取源文

## 架构

```
编辑表单字段 (翻译按钮)
  → SchemaForm onTranslate
  → POST /api/llm/translate
  → AppRuntime.translator + TranslationCache
  → 响应写回 field.handleChange
  → UnsavedChangesBar → PATCH /api/metadata/{id}
```

翻译能力挂在 LLM 资源下, 不绑定 metadata id. 持久化仍走既有 metadata PATCH.

## API

### `POST /api/llm/translate`

新路由模块 `src/amane/api/routes/llm.py`, 在 `routes/__init__.py` 注册.

请求体互斥:

| 形态 | 字段 | 用途 |
|------|------|------|
| 标量 | `field` + `text: str` | title / plot / studio / publisher / series |
| 列表 | `field` + `texts: list[str]` | actors / tags / directors |

`field` 枚举限制为可译子集:
`title` | `plot` | `actors` | `directors` | `tags` | `series` | `studio` | `publisher`.

响应与请求同形: `{ "text": "…" }` 或 `{ "texts": ["…", …] }`.
`texts` 与输入等长; 单项无需翻译、返回 `None` 或抛错时该位回填原文.

| 条件 | 状态 |
|------|------|
| LLM 未启用或缺密钥 (`translator is None`) | 503 |
| `scraping.field_language` 无该 field 目标语 | 422 |
| `text`/`texts` 同时缺席或同时出现 / 空串列表 | 422 |
| 翻译过程异常 | 503 (detail 中文) |

目标语取自 `config.scraping.field_language[field]`, 与刮削一致.
默认读/写既有 `TranslationCache`; 限速复用 `llm.rate_limit`.
请求内 `await`, 不创建 Task.

### Translator 提示词

在 `translator._FIELD_HINT` 为 actors / directors / tags / series / studio / publisher
补充词级提示 (保留专有名词、人名不强行意译等). 刮削 `_translate_metadata`
仍只按 `llm.translate_fields` 处理 title/plot, 本 API 与之解耦.

### Schema 标记

`PartialMetadata` 的 `json_schema_extras` 为上述 8 字段设置 `x-translate: true`
(经 `anyof_extras` / 既有 extras 工具). `GET /api/metadata/schema` 下发后,
前端以该扩展决定是否渲染翻译按钮.

## 前端

### Schema 类型

`schema/types.ts` 增加 `"x-translate"?: boolean` (text 与 array 扩展均可带).

### SchemaForm

新增可选 `onTranslate`:

```ts
onTranslate?: (args: {
  field: string;
  text?: string;
  texts?: string[];
}) => Promise<{ text?: string; texts?: string[] }>;
```

经 React context 下传给叶子字段. 未提供时即使有 `x-translate` 也不显示按钮
(设置页等不受影响).

### TextField

- 有 `x-translate` 且 `onTranslate` 且当前值非空: 显示翻译按钮 (替代 Clear)
- 无 `x-translate` 的可空标量: 仍显示 Clear; Clear 文案收入 i18n, 禁止硬编码英文
- 点击: loading → 调用 `onTranslate({ field: name, text })` → `handleChange(结果.text)`

### SimpleArrayField

- 有 `x-translate` 且 `onTranslate` 且数组非空: 控件旁显示翻译按钮
- 点击: loading → `onTranslate({ field: name, texts })` → `handleChange(结果.texts)`

### 影片编辑弹窗

`meta.$metadataId.tsx` 的 `SchemaForm` 传入 `onTranslate`, 内部调用生成的
`translateLlm` (或等价) client. 错误用既有通知展示; 成功仅改表单, 走 affix 保存条.

### i18n

- `common:actions.translate` → zh-CN 文案 `翻译`, en 文案 `Translate`
- `common:actions.clear` → 供 Clear 复用 (若尚无则补齐)

## 文档同步

实现后更新 (只写现行约定, 不写沿革):

- `docs/dev/llm.md` — 手工即时翻译端口与刮削嵌入点并列
- `docs/dev/api.md` — 路由表增加 `llm`
- `docs/dev/frontend.md` — Schema 表单 `x-translate` 与 Clear/翻译互斥规则 (若跨文件契约需要)

## 测试

- 后端表测试: 标量 / 列表成功路径; translator 缺失 503; 缺目标语 422;
  互斥 body 422; 列表单项失败回填原文; 缓存命中不二次 ask
- 前端: 优先覆盖 TextField / SimpleArrayField 在 `x-translate` 下的按钮可见性与
  `handleChange` 写入 (若仓库已有 schema-form 测试习惯); 无既有模式则以后端契约测试为主

## 验收

1. 打开影片编辑, 上述 8 字段在有内容时可见翻译按钮, 可空标量无 Clear
2. 点翻译后字段变为译文且出现未保存条; 确认保存后详情展示译文
3. LLM 关闭时点翻译得到明确错误, 表单不变
4. 不产生新的刮削 / 翻译类 Task; 剧照封面等资源 URL 不变
