import sys
from types import SimpleNamespace

import pytest

import app as writing_app


def test_homepage_and_status(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = writing_app.app.test_client()

    homepage = client.get("/")
    assert homepage.status_code == 200
    assert "Bản nháp tốt hơn" in homepage.get_data(as_text=True)
    assert 'id="level-select"' in homepage.get_data(as_text=True)
    assert client.get("/api/status").json == {
        "deep_available": False,
        "max_chars": writing_app.MAX_CHARS,
    }


def test_local_edit_preserves_meaning_and_reports_changes():
    client = writing_app.app.test_client()
    response = client.post(
        "/api/rewrite",
        json={
            "text": "nhằm mục đích cải thiện nhóm, chúng tôi  có khả năng xử lý 12 báo cáo.",
            "tone": "natural",
            "mode": "local",
        },
    )
    assert response.status_code == 200
    data = response.json
    assert data["mode"] == "local"
    assert data["result"] == "Để cải thiện nhóm, chúng tôi có thể xử lý 12 báo cáo."
    assert data["edit_count"] > 0
    assert data["notes"]


def test_local_edit_keeps_paragraphs_and_technical_data():
    edited, _, _ = writing_app.local_edit(
        "Báo cáo Q3 ghi 1.250 đơn hàng.\n\nTrong trường hợp tỷ lệ lỗi tăng, kiểm tra SKU-42.",
        "professional",
    )
    assert "1.250" in edited
    assert "SKU-42" in edited
    assert "\n\n" in edited
    assert "Nếu tỷ lệ lỗi tăng" in edited


def test_published_examples_match_basic_editor():
    hero, _, _ = writing_app.local_edit(
        "Nhằm mục đích cải thiện hiệu quả công việc, chúng tôi sẽ thực hiện việc xem xét lại quy trình hiện tại.",
        "natural",
    )
    example, _, _ = writing_app.local_edit(
        "Trong bối cảnh hiện nay, việc đưa ra các quyết định dựa trên dữ liệu đóng vai trò quan trọng đối với sự phát triển của doanh nghiệp.",
        "concise",
    )
    assert hero == "Để làm việc hiệu quả hơn, chúng tôi sẽ xem lại quy trình hiện tại."
    assert example == "Hiện nay, quyết định dựa trên dữ liệu quan trọng với sự phát triển của doanh nghiệp."


def test_natural_edit_changes_school_paragraph_without_dropping_key_details():
    original = (
        "Ngôi trường tiểu học thân yêu đã gắn bó với em trong suốt mấy năm qua là một nơi vô cùng đẹp đẽ và ấm áp. "
        "Từ xa nhìn lại, trường nổi bật với mái ngói đỏ tươi và bức tường màu vàng kem sáng sủa. "
        "Sân trường rộng rãi, được lát gạch sạch sẽ và rợp bóng mát của những cây bàng, cây phượng cổ thụ. "
        "Mỗi giờ ra chơi, sân trường lại vang lên tiếng cười nói rộn rã của chúng em bên những trò chơi dân gian và ghế đá dưới gốc cây. "
        "Các phòng học đều được trang bị đầy đủ bàn ghế gọn gàng, quạt mát và ánh sáng tràn ngập qua ô cửa sổ lớn. "
        "Em luôn yêu quý ngôi trường này như ngôi nhà thứ hai của mình và hứa sẽ học tập thật chăm chỉ để không phụ lòng thầy cô."
    )
    response = writing_app.app.test_client().post(
        "/api/rewrite", json={"text": original, "tone": "natural", "mode": "local"}
    )
    assert response.status_code == 200
    data = response.json
    assert data["changed"] is True
    assert data["edit_count"] >= 5
    assert data["result"] != original
    assert "Từ xa, mái ngói đỏ tươi" in data["result"]
    assert "Em hứa sẽ chăm chỉ học tập" in data["result"]
    assert "".join(part["text"] for part in data["segments"]) == data["result"]
    assert any(part["changed"] for part in data["segments"])
    for detail in ("mái ngói đỏ tươi", "cây bàng", "cây phượng", "thầy cô"):
        assert detail in data["result"]


def test_no_match_is_reported_as_no_change():
    response = writing_app.app.test_client().post(
        "/api/rewrite", json={"text": "Báo cáo Q3 ghi 1.250 đơn hàng.", "tone": "natural", "mode": "local"}
    )
    assert response.status_code == 200
    assert response.json["changed"] is False
    assert response.json["edit_count"] == 0
    assert not any(part["changed"] for part in response.json["segments"])
    assert "chưa tìm thấy" in response.json["notes"][0]


def test_rewrite_validates_input(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = writing_app.app.test_client()
    assert client.post("/api/rewrite", json={"text": "  "}).status_code == 400
    assert client.post("/api/rewrite", json={"text": "x" * 12001}).status_code == 400
    assert client.post("/api/rewrite", json={"text": "Hi", "tone": "unknown"}).status_code == 400
    assert client.post("/api/rewrite", json={"text": "Hi", "mode": "deep"}).status_code == 400
    assert client.post("/api/rewrite", json={"text": "Hi", "level": "unknown"}).status_code == 400


@pytest.mark.parametrize("level", ["light", "medium", "strong"])
def test_deep_mode_passes_rewrite_level(monkeypatch, level):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(
        writing_app,
        "deep_edit",
        lambda text, tone, chosen_level: calls.append((text, tone, chosen_level)) or "Bản mới: " + text,
    )
    client = writing_app.app.test_client()
    response = client.post(
        "/api/rewrite", json={"text": "Nội dung", "tone": "academic", "mode": "deep", "level": level}
    )
    assert response.status_code == 200
    assert response.json["result"] == "Bản mới: Nội dung"
    assert response.json["mode"] == "deep"
    assert response.json["level"] == level
    assert response.json["changed"] is True
    assert calls == [("Nội dung", "academic", level)]


@pytest.mark.parametrize("level,expected", [
    ("light", "Giữ gần nguyên cấu trúc câu"),
    ("medium", "viết lại những câu dài hoặc gượng"),
    ("strong", "diễn đạt lại rõ rệt"),
])
def test_ai_instructions_match_selected_level(monkeypatch, level, expected):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "test-key"
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text="Câu đã sửa.")

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    assert writing_app.deep_edit("Câu gốc.", "natural", level) == "Câu đã sửa."
    assert expected.casefold() in calls[0]["instructions"].casefold()
    assert "Giữ nguyên từng tên riêng" in calls[0]["instructions"]
    assert calls[0]["input"] == "Câu gốc."
    assert calls[0]["store"] is False


def test_ai_rejects_changed_protected_details(monkeypatch):
    source = 'Nguyễn Văn An gửi 1.250 đơn hàng SKU-42 tới Hà Nội ngày 12/10/2026 và ghi "đã kiểm tra".'
    safe = 'Ngày 12/10/2026, Nguyễn Văn An gửi 1.250 đơn hàng SKU-42 tới Hà Nội và ghi "đã kiểm tra".'
    assert writing_app.preserved_details(source, safe)
    assert not writing_app.preserved_details(source, safe.replace("1.250", "1.200"))
    assert not writing_app.preserved_details(source, safe.replace("Nguyễn Văn An", "Nguyễn Văn Bình"))
    assert not writing_app.preserved_details(source, safe.replace('"đã kiểm tra"', '"đang kiểm tra"'))

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(writing_app, "deep_edit", lambda text, tone, level: safe.replace("SKU-42", "SKU-43"))
    response = writing_app.app.test_client().post(
        "/api/rewrite", json={"text": source, "mode": "deep", "level": "strong"}
    )
    assert response.status_code == 502
    assert "làm mất" in response.json["error"]
    assert "result" not in response.json
