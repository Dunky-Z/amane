"""/metadata/batch/* HTTP 接线. 删除级联 / 挂载语义见 tests/db."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from amane.db.models import TaskType

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


@pytest_asyncio.fixture(autouse=True)
async def _seed_library(repo: Repository) -> None:
    if await repo.get_library(1) is None:
        await repo.create_library(name="default", path="/")


class TestMetadataBatchHttp:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_batch_delete(self, client: AsyncClient, repo: Repository):
        m1 = await repo.upsert_metadata(number="BD-001")
        m2 = await repo.upsert_metadata(number="BD-002")
        assert m1.id is not None and m2.id is not None
        resp = await client.post("metadata/batch/delete", json={"ids": [m1.id, m2.id, 9999]})
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 2, "missing": 1, "failed": 0}
        assert (await client.post("metadata/batch/delete", json={"ids": [8888]})).json() == {
            "deleted": 0,
            "missing": 1,
            "failed": 0,
        }
        assert (await client.post("metadata/batch/delete", json={"ids": []})).status_code == 422

    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_source_files(self, client: AsyncClient, repo: Repository, tmp_path: Path):
        meta = await repo.upsert_metadata(number="DEL-FILE-001")
        kept = await repo.upsert_metadata(number="DEL-FILE-002")
        blocked = await repo.upsert_metadata(number="DEL-FILE-003")
        assert meta.id is not None and kept.id is not None and blocked.id is not None
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"video")
        media = await repo.create_media_file(library_id=1, path=str(video), metadata_id=meta.id)
        assert media.id is not None
        untouched = tmp_path / "stay.mp4"
        untouched.write_bytes(b"stay")
        stay = await repo.create_media_file(library_id=1, path=str(untouched), metadata_id=kept.id)
        assert stay.id is not None
        folder = tmp_path / "not-a-file"
        folder.mkdir()
        await repo.create_media_file(library_id=1, path=str(folder), metadata_id=blocked.id)

        only_meta = await client.delete(f"metadata/{kept.id}")
        assert only_meta.status_code == 204
        assert untouched.is_file()
        assert await repo.get_media_file(stay.id) is not None

        rejected = await client.delete(f"metadata/{blocked.id}", params={"delete_files": True})
        assert rejected.status_code == 409
        assert folder.is_dir()
        assert await repo.get_metadata(blocked.id) is not None

        removed = await client.delete(f"metadata/{meta.id}", params={"delete_files": True})
        assert removed.status_code == 204, removed.text
        assert not video.exists()
        assert await repo.get_metadata(meta.id) is None
        assert await repo.get_media_file(media.id) is None

        ok_meta = await repo.upsert_metadata(number="DEL-FILE-004")
        bad_meta = await repo.upsert_metadata(number="DEL-FILE-005")
        assert ok_meta.id is not None and bad_meta.id is not None
        ok_video = tmp_path / "batch.mp4"
        ok_video.write_bytes(b"batch")
        await repo.create_media_file(library_id=1, path=str(ok_video), metadata_id=ok_meta.id)
        bad_dir = tmp_path / "batch-dir"
        bad_dir.mkdir()
        await repo.create_media_file(library_id=1, path=str(bad_dir), metadata_id=bad_meta.id)
        batch = await client.post(
            "metadata/batch/delete",
            json={"ids": [ok_meta.id, bad_meta.id, 9999], "delete_files": True},
        )
        assert batch.status_code == 200, batch.text
        assert batch.json() == {"deleted": 1, "missing": 1, "failed": 1}
        assert not ok_video.exists()
        assert bad_dir.is_dir()
        assert await repo.get_metadata(bad_meta.id) is not None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_batch_scrape(self, client: AsyncClient, repo: Repository, stop_worker: None):
        m1 = await repo.upsert_metadata(number="BS-001")
        m2 = await repo.upsert_metadata(number="BS-002")
        assert m1.id is not None and m2.id is not None
        resp = await client.post("metadata/batch/scrape", json={"ids": [m1.id, m2.id, 9999]})
        assert resp.status_code == 202
        data = resp.json()
        assert data["submitted"] == 2
        assert data["missing"] == 1
        assert len(data["task_ids"]) == 2
        numbers = set()
        for task_id in data["task_ids"]:
            task = await repo.get_task(task_id)
            assert task is not None
            assert task.type == TaskType.SCRAPE
            numbers.add(task.payload["number"])
        assert numbers == {"BS-001", "BS-002"}
        task = await repo.get_task(data["task_ids"][0])
        assert task is not None
        assert task.payload["content_type"] == "censored"
        assert set(task.payload["use_cache"]) == {"metadata", "trans"}

        custom_meta = await repo.upsert_metadata(number="BS-004")
        assert custom_meta.id is not None
        custom = await client.post(
            "metadata/batch/scrape", json={"ids": [custom_meta.id], "content_type": "uncensored", "use_cache": []}
        )
        custom_task = await repo.get_task(custom.json()["task_ids"][0])
        assert custom_task is not None
        assert custom_task.payload["content_type"] == "uncensored"
        assert custom_task.payload["use_cache"] == []

        missing = await client.post("metadata/batch/scrape", json={"ids": [9999]})
        assert missing.status_code == 202
        assert missing.json() == {"submitted": 0, "missing": 1, "task_ids": []}
        assert (await client.post("metadata/batch/scrape", json={"ids": []})).status_code == 422

    @pytest.mark.asyncio(loop_scope="function")
    async def test_batch_user_tags(self, client: AsyncClient, repo: Repository):
        tags, _created = await repo.ensure_user_tags(["watched"])
        tag = tags[0]
        assert tag.id is not None
        m1 = await repo.upsert_metadata(number="BT-001")
        m2 = await repo.upsert_metadata(number="BT-002")
        assert m1.id is not None and m2.id is not None
        resp = await client.post(
            "metadata/batch/user-tags",
            json={"ids": [m1.id, m2.id, 9999], "user_tag_ids": [tag.id], "action": "attach"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"changed": 2, "unchanged": 0, "missing": 1}
        detail = await client.get(f"metadata/{m1.id}")
        assert any(t["name"] == "watched" for t in detail.json()["user_tags"])

        detach = await client.post(
            "metadata/batch/user-tags",
            json={"ids": [m1.id, m2.id], "user_tag_ids": [tag.id], "action": "detach"},
        )
        assert detach.json() == {"changed": 2, "unchanged": 0, "missing": 0}
        # 未挂载的条目在 detach 时计入 unchanged, 不是错误
        assert (
            await client.post(
                "metadata/batch/user-tags", json={"ids": [m1.id], "user_tag_ids": [tag.id], "action": "detach"}
            )
        ).json() == {"changed": 0, "unchanged": 1, "missing": 0}
        # 未知标签是请求级错误, 整请求不生效
        unknown = await client.post(
            "metadata/batch/user-tags", json={"ids": [m1.id], "user_tag_ids": [9999], "action": "attach"}
        )
        assert unknown.status_code == 404
        assert (
            await client.post("metadata/batch/user-tags", json={"ids": [m1.id], "user_tag_ids": [], "action": "attach"})
        ).status_code == 422
        assert (
            await client.post(
                "metadata/batch/user-tags", json={"ids": [m1.id], "user_tag_ids": [tag.id], "action": "bogus"}
            )
        ).status_code == 422
        assert (
            await client.post(
                "metadata/batch/user-tags", json={"ids": [], "user_tag_ids": [tag.id], "action": "attach"}
            )
        ).status_code == 422
