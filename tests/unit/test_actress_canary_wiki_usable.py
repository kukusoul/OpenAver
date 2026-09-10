"""_wiki_ja_usable() 離線守衛（CD-145b-14）——不需要真連線。

canary 的可用判準必須跟 sink（core/actress_photo.py 的 validate_photo_url，換圖下載
前的真正閘門）逐字相同，不是自己在 canary 裡寫一份近似判斷（BE-GUARD-01）。這四格
鎖住「文字有值 且 photo_url 過白名單」這個組合邏輯，不連真實 wikipedia——真連線驗證
是 tests/smoke/test_actress_canary.py::test_wiki_ja_canary 自己的事（CI 不跑，owner
本機 `pytest tests/smoke -m smoke` 才會跑到）。

`birth` 是 core/scrapers/actress/orchestrator.py 的 _MEANINGFUL_TEXT_FIELDS 之一
（`name_ja`／`photo_url`／`photo_license` 單獨出現不算「有意義的文字」，見該模組
_has_meaningful_text() 的 docstring）——前三筆假資料都用它讓 _has_meaningful_text 那一半
恆為 True，讓 photo_url 白名單那一半成為唯一的分岔點。第四筆反向：文字欄位全空
（沒有任何 _MEANINGFUL_TEXT_FIELDS 有值；`name_ja` 故意帶值也不算）但 photo_url 仍是
合法 upload.wikimedia.org 原圖，鎖住 AND 的文字那一半——拿掉 `_has_meaningful_text`
時只有這一筆會轉紅。
"""
from tests.smoke.test_actress_canary import _wiki_ja_usable


def test_wiki_ja_usable_true_when_text_and_upload_host():
    # 驗收：文字有值 且 photo_url 是 upload.wikimedia.org 原圖形狀 -> True
    result = {
        "birth": "1990-01-01",
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/8/85/Foo.jpg",
    }
    assert _wiki_ja_usable(result) is True


def test_wiki_ja_usable_false_when_photo_url_is_thumb_host():
    # T8 修好之前的壞形狀：文字抓得到，但 photo_url 還停在 thumb.wikimedia.org 縮圖
    # 網址，過不了 validate_photo_url() 白名單（只認 upload.wikimedia.org）。
    result = {
        "birth": "1990-01-01",
        "photo_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/8/85/Foo.jpg/250px-Foo.jpg",
    }
    assert _wiki_ja_usable(result) is False


def test_wiki_ja_usable_false_when_photo_url_empty():
    # 文字有值，但 photo_url 是空字串（例如頁面 infobox 沒有符合條件的圖片）-> False
    result = {"birth": "1990-01-01", "photo_url": ""}
    assert _wiki_ja_usable(result) is False


def test_wiki_ja_usable_false_when_text_empty_and_upload_host():
    # 反向：_MEANINGFUL_TEXT_FIELDS 全空（name_ja 不在那個集合裡），但 photo_url
    # 是合法 upload.wikimedia.org 原圖 -> False。拿掉 AND 的文字那一半時只有這筆轉紅。
    result = {
        "name_ja": "三上悠亜",
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/8/85/Foo.jpg",
        "photo_license": "CC BY-SA 4.0",
    }
    assert _wiki_ja_usable(result) is False
