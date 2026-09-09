"""POST /llm/translate: 状态码、互斥 body、标量/列表回填. 不触网."""

from typing import TYPE_CHECKING

import pytest

from amane.enums import Language, MetadataField

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx2 import AsyncClient


class _FakeTranslator:
    def __init__(self, *, mapping: dict[str, str] | None = None, fail: set[str] | None = None) -> None:
        self.mapping = mapping or {}
        self.fail = fail or set()
        self.calls: list[tuple[str, Language, MetadataField]] = []

    async def translate(
        self, text: str, target: Language, field: MetadataField, *, use_cache: bool = True
    ) -> str | None:
        self.calls.append((text, target, field))
        if text in self.fail:
            raise RuntimeError("boom")
        return self.mapping.get(text)


class TestLlmTranslateHttp:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_translate_contract(self, client: AsyncClient, app: FastAPI):
        # 默认未启用 LLM → 503
        assert (await client.post("llm/translate", json={"field": "title", "text": "Hello"})).status_code == 503

        # 互斥 / 空 / 非法字段 → 422
        cases = [
            {"field": "title"},
            {"field": "title", "text": "a", "texts": ["b"]},
            {"field": "title", "text": "  "},
            {"field": "actors", "texts": []},
            {"field": "actors", "texts": ["ok", "  "]},
            {"field": "score", "text": "Hello"},
            {"field": "poster_urls", "texts": ["x"]},
        ]
        for body in cases:
            resp = await client.post("llm/translate", json=body)
            assert resp.status_code == 422, body

        translator = _FakeTranslator(
            mapping={"Hello world": "你好世界", "Alice": "爱丽丝"},
            fail={"Boom"},
        )
        app.state.runtime.translator = translator

        # 标量成功
        ok = await client.post("llm/translate", json={"field": "title", "text": "Hello world"})
        assert ok.status_code == 200
        assert ok.json() == {"text": "你好世界", "texts": None}

        # 无需翻译 (mapping 无键 → None) 回填原文
        keep = await client.post("llm/translate", json={"field": "title", "text": "Already CN"})
        assert keep.status_code == 200
        assert keep.json()["text"] == "Already CN"

        # 标量翻译抛错 → 503
        assert (await client.post("llm/translate", json={"field": "title", "text": "Boom"})).status_code == 503

        # 列表: 成功项译出, 失败项回填原文
        batch = await client.post(
            "llm/translate",
            json={"field": "actors", "texts": ["Alice", "Boom", "Bob"]},
        )
        assert batch.status_code == 200
        assert batch.json()["texts"] == ["爱丽丝", "Boom", "Bob"]

        # 缺目标语 → 422
        app.state.runtime.config.hot.scraping.field_language = {MetadataField.TITLE: Language.ZH_CN}
        missing = await client.post("llm/translate", json={"field": "actors", "texts": ["Alice"]})
        assert missing.status_code == 422
        assert "目标语言" in missing.json()["detail"]


class TestMetadataSchemaTranslate:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_x_translate_on_editable_fields(self, client: AsyncClient):
        schema = (await client.get("metadata/schema")).json()
        props = schema["properties"]
        for key in ("title", "plot", "actors", "directors", "tags", "series", "studio", "publisher"):
            any_of = props[key]["anyOf"]
            non_null = next(s for s in any_of if s.get("type") != "null")
            assert non_null.get("x-translate") is True, key
        # 非可译字段无标记
        release = next(s for s in props["release"]["anyOf"] if s.get("type") != "null")
        assert "x-translate" not in release
