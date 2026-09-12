"""影片写库填空合并单元测试."""

from __future__ import annotations

from amane.aggregate.film_merge import film_fields_from_aggregate, merge_film_rows_fill_empty
from amane.aggregate.models import AggregatedMetadata, SourcedScore
from amane.crawlers.models import FilmActor
from amane.db.models import Metadata
from amane.enums import ActorGender


def _existing(**kwargs: object) -> Metadata:
    return Metadata(number="ABC-123", **kwargs)  # type: ignore[arg-type]


def _incoming(**kwargs: object) -> AggregatedMetadata:
    return AggregatedMetadata(number="ABC-123", **kwargs)  # type: ignore[arg-type]


class TestMergeFilmRowsFillEmpty:
    def test_keeps_existing_plot_when_new_empty(self) -> None:
        existing = _existing(plot="旧简介", title="旧标题")
        incoming = _incoming(title="新标题", plot=None)
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={"title": "javdb"},
        )
        assert out.plot == "旧简介"
        assert out.title == "旧标题"
        assert "title" not in out.field_sources

    def test_fills_empty_plot(self) -> None:
        existing = _existing(plot=None, field_sources={})
        incoming = _incoming(plot="新简介")
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={"plot": "dmm"},
        )
        assert out.plot == "新简介"
        assert out.field_sources["plot"] == "dmm"

    def test_keeps_extrafanart_and_raw_for_missing_site(self) -> None:
        existing = _existing(
            extrafanart_urls={"dmm": ["https://d/1.jpg", "https://d/2.jpg"]},
            raw={"dmm": {"title": "旧"}, "mgstage": {"title": "旧2"}},
        )
        incoming = _incoming(extrafanart_urls={"javdb": ["https://j/1.jpg"]}, title="仅 javdb")
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={"javdb": {"title": "新"}},
            field_sources={"title": "javdb"},
        )
        assert out.extrafanart_urls["dmm"] == ["https://d/1.jpg", "https://d/2.jpg"]
        assert out.extrafanart_urls["javdb"] == ["https://j/1.jpg"]
        assert out.raw["dmm"]["title"] == "旧"
        assert out.raw["javdb"]["title"] == "新"
        assert out.raw["mgstage"]["title"] == "旧2"

    def test_updates_extrafanart_when_site_returns_nonempty(self) -> None:
        existing = _existing(extrafanart_urls={"dmm": ["https://old/1.jpg"]})
        incoming = _incoming(extrafanart_urls={"dmm": ["https://new/1.jpg", "https://new/2.jpg"]})
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={"dmm": {}},
            field_sources={},
        )
        assert out.extrafanart_urls["dmm"] == ["https://new/1.jpg", "https://new/2.jpg"]

    def test_url_union_preserves_old_order(self) -> None:
        existing = _existing(poster_urls=["https://old/a.jpg", "https://old/b.jpg"])
        incoming = _incoming()
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=["https://old/b.jpg", "https://new/c.jpg"],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={},
        )
        assert out.poster_urls == ["https://old/a.jpg", "https://old/b.jpg", "https://new/c.jpg"]

    def test_url_keeps_old_when_new_empty(self) -> None:
        existing = _existing(thumb_urls=["https://old/t.jpg"])
        out = merge_film_rows_fill_empty(
            existing,
            _incoming(),
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={},
        )
        assert out.thumb_urls == ["https://old/t.jpg"]

    def test_keeps_nonempty_actors_list(self) -> None:
        existing = _existing(actors=["甲"])
        incoming = _incoming(actors=[FilmActor(name="乙", gender=ActorGender.FEMALE)])
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={},
        )
        assert out.actors == ["甲"]

    def test_scores_setdefault(self) -> None:
        existing = _existing(scores={"dmm": 80.0})
        incoming = _incoming(scores=[SourcedScore(site="javdb", score=90.0), SourcedScore(site="dmm", score=99.0)])
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={},
        )
        assert out.scores == {"dmm": 80.0, "javdb": 90.0}

    def test_field_sources_existing_wins(self) -> None:
        existing = _existing(plot="旧", field_sources={"plot": "dmm"})
        incoming = _incoming(plot="新", title="新标题")
        out = merge_film_rows_fill_empty(
            existing,
            incoming,
            poster_urls=[],
            thumb_urls=[],
            trailer_urls=[],
            raw={},
            field_sources={"plot": "javdb", "title": "javdb"},
        )
        assert out.field_sources["plot"] == "dmm"
        assert out.title == "新标题"
        assert out.field_sources["title"] == "javdb"


class TestFilmFieldsFromAggregate:
    def test_passthrough(self) -> None:
        incoming = _incoming(title="T", plot="P", actors=[FilmActor(name="A")])
        out = film_fields_from_aggregate(
            incoming,
            poster_urls=["https://p.jpg"],
            thumb_urls=[],
            trailer_urls=[],
            raw={"dmm": {"title": "T"}},
            field_sources={"title": "dmm"},
        )
        assert out.title == "T"
        assert out.actors == ["A"]
        assert out.poster_urls == ["https://p.jpg"]
        assert out.raw["dmm"]["title"] == "T"
