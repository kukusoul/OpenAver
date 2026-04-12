"""Tests for Actress dataclass and ActressRepository in core/database.py"""
import time
import pytest
from pathlib import Path

from core.database import init_db, Actress, ActressRepository


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def repo(db_path: Path) -> ActressRepository:
    return ActressRepository(db_path)


# ---------------------------------------------------------------------------
# save() + get_by_name()
# ---------------------------------------------------------------------------

def test_save_and_get_by_name(repo):
    actress = Actress(name="深田えいみ", name_en="Eimi Fukada", height="163cm")
    repo.save(actress)

    result = repo.get_by_name("深田えいみ")
    assert result is not None
    assert result.name == "深田えいみ"
    assert result.name_en == "Eimi Fukada"
    assert result.height == "163cm"


def test_get_by_name_not_found(repo):
    result = repo.get_by_name("不存在的人")
    assert result is None


# ---------------------------------------------------------------------------
# save() ON CONFLICT: updated_at 更新, created_at 保留（CD-12）
# ---------------------------------------------------------------------------

def test_save_upsert_preserves_created_at(repo):
    actress = Actress(name="三上悠亞", height="157cm")
    repo.save(actress)

    first = repo.get_by_name("三上悠亞")
    assert first is not None
    created_at_first = first.created_at
    updated_at_first = first.updated_at

    # 稍等確保 CURRENT_TIMESTAMP 有機會不同
    time.sleep(1.1)

    actress2 = Actress(name="三上悠亞", height="158cm")
    repo.save(actress2)

    second = repo.get_by_name("三上悠亞")
    assert second is not None
    assert second.height == "158cm"
    # created_at 不變
    assert second.created_at == created_at_first
    # updated_at 應更新（或至少不早於第一次）
    assert second.updated_at >= updated_at_first


# ---------------------------------------------------------------------------
# delete_by_name()
# ---------------------------------------------------------------------------

def test_delete_by_name_existing(repo):
    repo.save(Actress(name="橋本ありな"))
    result = repo.delete_by_name("橋本ありな")
    assert result is True
    assert repo.get_by_name("橋本ありな") is None


def test_delete_by_name_not_existing(repo):
    result = repo.delete_by_name("不存在的人")
    assert result is False


# ---------------------------------------------------------------------------
# get_all()
# ---------------------------------------------------------------------------

def test_get_all_correct_count(repo):
    repo.save(Actress(name="女優A"))
    repo.save(Actress(name="女優B"))
    repo.save(Actress(name="女優C"))

    all_actresses = repo.get_all()
    assert len(all_actresses) == 3


def test_get_all_empty(repo):
    assert repo.get_all() == []


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------

def test_exists_true(repo):
    repo.save(Actress(name="波多野結衣"))
    assert repo.exists("波多野結衣") is True


def test_exists_false(repo):
    assert repo.exists("不存在的人") is False


# ---------------------------------------------------------------------------
# JSON 欄位（aliases, tags）序列化/反序列化
# ---------------------------------------------------------------------------

def test_json_fields_roundtrip(repo):
    actress = Actress(
        name="夢乃あいか",
        aliases=["ゆめのあいか", "Aika Yumeno"],
        tags=["美少女", "スレンダー"],
    )
    repo.save(actress)

    result = repo.get_by_name("夢乃あいか")
    assert result is not None
    assert result.aliases == ["ゆめのあいか", "Aika Yumeno"]
    assert result.tags == ["美少女", "スレンダー"]


def test_json_fields_empty_list_default(repo):
    actress = Actress(name="新ありな")
    repo.save(actress)

    result = repo.get_by_name("新ありな")
    assert result is not None
    assert result.aliases == []
    assert result.tags == []


# ---------------------------------------------------------------------------
# bust/waist/hip None 值正確處理
# ---------------------------------------------------------------------------

def test_measurements_none(repo):
    actress = Actress(name="測試女優A")
    repo.save(actress)

    result = repo.get_by_name("測試女優A")
    assert result is not None
    assert result.bust is None
    assert result.waist is None
    assert result.hip is None


def test_measurements_with_values(repo):
    actress = Actress(name="測試女優B", bust=88, waist=58, hip=86)
    repo.save(actress)

    result = repo.get_by_name("測試女優B")
    assert result is not None
    assert result.bust == 88
    assert result.waist == 58
    assert result.hip == 86
