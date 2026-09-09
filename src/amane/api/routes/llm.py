"""同步 LLM 翻译. 不入任务队列, 不写 metadata."""

from fastapi import APIRouter, HTTPException

from ...enums import MetadataField
from ..deps import ConfigDep, RuntimeDep
from ..models.llm import TranslateRequest, TranslateResponse

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/translate")
async def translate_text(req: TranslateRequest, runtime: RuntimeDep, config: ConfigDep) -> TranslateResponse:
    translator = runtime.translator
    if translator is None:
        raise HTTPException(status_code=503, detail="LLM 翻译未启用或未配置密钥")

    target = config.hot.scraping.field_language.get(req.field)
    if target is None:
        raise HTTPException(status_code=422, detail=f"未配置字段目标语言: {req.field}")

    field: MetadataField = req.field

    if req.text is not None:
        try:
            result = await translator.translate(req.text, target, field)
        except Exception:
            raise HTTPException(status_code=503, detail="翻译失败") from None
        return TranslateResponse(text=result if result else req.text)

    assert req.texts is not None
    out: list[str] = []
    for item in req.texts:
        try:
            result = await translator.translate(item, target, field)
            out.append(result if result else item)
        except Exception:
            out.append(item)
    return TranslateResponse(texts=out)
