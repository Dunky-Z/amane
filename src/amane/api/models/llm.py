"""即时翻译请求/响应. 不落库, 由编辑表单 dirty 保存."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...enums import MetadataField

# 与影片编辑 x-translate 字段对齐; 刮削 translate_fields 可更窄.
TRANSLATABLE_FIELDS: frozenset[MetadataField] = frozenset(
    {
        MetadataField.TITLE,
        MetadataField.PLOT,
        MetadataField.ACTORS,
        MetadataField.DIRECTORS,
        MetadataField.TAGS,
        MetadataField.SERIES,
        MetadataField.STUDIO,
        MetadataField.PUBLISHER,
    }
)


class TranslateRequest(BaseModel):
    field: MetadataField = Field(description="元数据字段; 须为可译子集")
    text: str | None = Field(default=None, description="标量原文; 与 texts 互斥")
    texts: list[str] | None = Field(default=None, description="列表原文; 与 text 互斥")

    @model_validator(mode="after")
    def _validate_payload(self) -> Self:
        if self.field not in TRANSLATABLE_FIELDS:
            raise ValueError(f"字段不可翻译: {self.field}")
        has_text = self.text is not None
        has_texts = self.texts is not None
        if has_text == has_texts:
            raise ValueError("须且仅能提供 text 或 texts 之一")
        if has_text:
            assert self.text is not None
            if not self.text.strip():
                raise ValueError("text 不能为空")
        else:
            assert self.texts is not None
            if len(self.texts) == 0:
                raise ValueError("texts 不能为空")
            if any(not item.strip() for item in self.texts):
                raise ValueError("texts 项不能为空")
        return self


class TranslateResponse(BaseModel):
    text: str | None = None
    texts: list[str] | None = None
