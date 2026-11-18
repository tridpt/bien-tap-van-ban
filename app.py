"""Text editing workspace with an optional OpenAI rewrite mode."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request


load_dotenv()
MAX_CHARS = 12_000
TONES = {"natural", "concise", "professional", "academic"}
REWRITE_LEVELS = {"light", "medium", "strong"}

LEVEL_INSTRUCTIONS = {
    "light": (
        "Mức nhẹ: chỉ sửa lỗi chính tả, dấu câu, ngữ pháp và một vài từ gây khó hiểu. "
        "Giữ gần nguyên cấu trúc câu, thứ tự ý, độ dài và giọng riêng của người viết."
    ),
    "medium": (
        "Mức vừa: viết lại những câu dài hoặc gượng, bỏ phần lặp và nối các ý cho mạch lạc. "
        "Có thể thay cấu trúc câu nhưng giữ thứ tự lập luận và giọng riêng của người viết."
    ),
    "strong": (
        "Mức mạnh: diễn đạt lại rõ rệt ở cấp độ câu và đoạn, cải thiện nhịp đọc và cách chuyển ý. "
        "Có thể sắp xếp lại câu trong cùng đoạn khi cần, nhưng giữ đầy đủ mọi ý, sắc thái và lập luận."
    ),
}

NUMBER_PATTERN = re.compile(r"(?<!\w)\d+(?:[.,:/-]\d+)*(?:\s*%)?")
IDENTIFIER_PATTERN = re.compile(r"\b(?:[A-Z]{2,}(?:-[A-Z0-9]+)*|[A-Z]{1,5}\d+[A-Z0-9-]*)\b")
URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
QUOTE_PATTERN = re.compile(r"[“\"]([^“”\"\n]+)[”\"]")
WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
app.json.ensure_ascii = False


@dataclass(frozen=True)
class EditRule:
    pattern: str
    replacement: str
    note: str


COMMON_RULES = (
    EditRule(r"\bnhằm mục đích\b", "để", "Rút gọn cách diễn đạt dài dòng"),
    EditRule(r"\btrong trường hợp\b", "nếu", "Dùng từ nối trực tiếp hơn"),
    EditRule(r"\bcó khả năng\b", "có thể", "Chọn cách nói gần gũi hơn"),
    EditRule(r"\bđóng vai trò quan trọng\b", "quan trọng", "Bỏ cụm từ thừa"),
    EditRule(r"\bcải thiện hiệu quả công việc\b", "làm việc hiệu quả hơn", "Diễn đạt tự nhiên hơn"),
    EditRule(r"\bthực hiện việc xem xét lại\b", "xem lại", "Bỏ cụm từ thừa"),
    EditRule(r"\bmột cách nhanh chóng\b", "nhanh", "Rút gọn trạng từ"),
    EditRule(r"\bin order to\b", "to", "Remove unnecessary wording"),
    EditRule(r"\bdue to the fact that\b", "because", "Use a more direct connection"),
    EditRule(r"\bin the event that\b", "if", "Use a more direct connection"),
    EditRule(r"\butilize\b", "use", "Choose a simpler word"),
)

CONCISE_RULES = (
    EditRule(r"\bbên cạnh đó\b", "ngoài ra", "Dùng từ nối ngắn hơn"),
    EditRule(r"\btrong bối cảnh hiện nay\b", "hiện nay", "Bỏ cụm mở đầu dài"),
    EditRule(r"\bviệc đưa ra các quyết định\b", "quyết định", "Nói trực tiếp hơn"),
    EditRule(r"\bđối với sự phát triển\b", "với sự phát triển", "Dùng giới từ đơn giản hơn"),
    EditRule(r"\ba number of\b", "several", "Reduce wordiness"),
    EditRule(r"\bat this point in time\b", "now", "Reduce wordiness"),
)

NATURAL_RULES = (
    EditRule(r"\btrong suốt\b", "suốt", "Làm câu gọn và tự nhiên hơn"),
    EditRule(r"\bvô cùng\b", "rất", "Giảm từ nhấn mạnh dài dòng"),
    EditRule(r"\bđẹp đẽ\b", "đẹp", "Dùng từ quen thuộc hơn"),
    EditRule(r"\btừ xa nhìn lại\b", "nhìn từ xa", "Đổi cách mở đầu câu"),
    EditRule(r"\bđược lát gạch sạch sẽ\b", "có nền gạch sạch sẽ", "Dùng cách nói chủ động hơn"),
    EditRule(r"\bmỗi giờ ra chơi\b", "vào giờ ra chơi", "Đổi cách mở đầu câu"),
    EditRule(r"\blại vang lên\b", "vang lên", "Bỏ từ lặp không cần thiết"),
    EditRule(r"\bđều được trang bị đầy đủ\b", "đều có đủ", "Nói trực tiếp hơn"),
    EditRule(r"\bánh sáng tràn ngập qua\b", "ánh sáng tràn vào từ", "Diễn đạt hình ảnh rõ hơn"),
    EditRule(r"\bhọc tập thật chăm chỉ\b", "chăm chỉ học tập", "Sắp xếp cụm từ tự nhiên hơn"),
)

PROFESSIONAL_RULES = (
    EditRule(r"\ba lot of\b", "many", "Use a more precise phrase"),
    EditRule(r"\bget in touch\b", "contact", "Use a more direct business phrase"),
)


def _match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def local_edit(text: str, tone: str) -> tuple[str, list[str], int]:
    """Apply restrained, deterministic edits without changing the argument."""
    notes: list[str] = []
    count = 0
    updated = text.replace("\r\n", "\n").replace("\r", "\n")

    trimmed = re.sub(r"[ \t]+(?=\n)", "", updated)
    trimmed = re.sub(r"[ \t]{2,}", " ", trimmed)
    trimmed = re.sub(r"\n{3,}", "\n\n", trimmed).strip()
    if trimmed != updated.strip():
        notes.append("Chuẩn hóa khoảng trắng và đoạn văn")
        count += 1
    updated = trimmed

    spaced = re.sub(r"[ \t]+([,.;!?])", r"\1", updated)
    spaced = re.sub(r"([,;!?])(?=[^\s\d\W])", r"\1 ", spaced, flags=re.UNICODE)
    if spaced != updated:
        notes.append("Sửa khoảng trắng quanh dấu câu")
        count += 1
    updated = spaced

    rules = list(COMMON_RULES)
    if tone == "concise":
        rules.extend(CONCISE_RULES)
    elif tone == "professional":
        rules.extend(PROFESSIONAL_RULES)
    elif tone == "natural":
        rules.extend(CONCISE_RULES[:1])
        rules.extend(NATURAL_RULES)

    for rule in rules:
        updated, replacements = re.subn(
            rule.pattern,
            lambda match, value=rule.replacement: _match_case(match.group(0), value),
            updated,
            flags=re.IGNORECASE,
        )
        if replacements:
            count += replacements
            if rule.note not in notes:
                notes.append(rule.note)

    if tone == "natural":
        # Reframe a few common long-sentence shapes while retaining their facts.
        structural_rules = (
            (
                r"(?P<subject>[^.!?]{8,100}?) đã gắn bó với (?P<person>em|tôi|mình) (?P<period>suốt [^.!?]{4,40}?) là một nơi (?P<description>[^.!?]{4,90})\.",
                lambda m: (f"{m['subject']} đã gắn bó với {m['person']} {m['period']}. "
                           f"Với {m['person']}, nơi ấy {m['description']}."),
                "Tách câu dài để dễ đọc",
            ),
            (
                r"Nhìn từ xa, (?P<subject>[^,.!?]{2,40}?) nổi bật với (?P<features>[^.!?]{8,150})\.",
                lambda m: f"Từ xa, {m['features']} khiến {m['subject']} nổi bật.",
                "Đổi thứ tự ý trong câu",
            ),
            (
                r"(?P<speaker>Em|Tôi|Mình) luôn yêu quý (?P<place>[^.!?]{8,100}?) như (?P<home>[^.!?]{8,100}?) và hứa sẽ (?P<promise>[^.!?]{8,100})\.",
                lambda m: (f"{m['speaker']} luôn yêu quý {m['place']} như {m['home']}. "
                           f"{m['speaker']} hứa sẽ {m['promise']}."),
                "Tách hai ý thành hai câu",
            ),
        )
        for pattern, replacement, note in structural_rules:
            updated, replacements = re.subn(pattern, replacement, updated, flags=re.IGNORECASE)
            if replacements:
                count += replacements
                if note not in notes:
                    notes.append(note)

    # Capitalize only sentence openings. Keep names and the rest of each sentence intact.
    capitalized = re.sub(
        r"(^|[.!?][ \t]+|\n)([a-zà-ỹ])",
        lambda match: match.group(1) + match.group(2).upper(),
        updated,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if capitalized != updated:
        updated = capitalized
        count += 1
        notes.append("Viết hoa đầu câu")

    if not notes:
        notes.append("Quy tắc cơ bản chưa tìm thấy chỗ có thể sửa trong đoạn này.")
    return updated, notes, count


def changed_segments(original: str, result: str) -> list[dict[str, object]]:
    """Return safe text chunks for highlighting edits in the output panel."""
    source_words = re.findall(r"\S+\s*", original)
    result_words = re.findall(r"\S+\s*", result)
    if len(source_words) > 1500 or len(result_words) > 1500:
        return [{"text": result, "changed": False}]

    matcher = SequenceMatcher(None, source_words, result_words, autojunk=True)
    chunks: list[dict[str, object]] = []
    for operation, _start_a, _end_a, start_b, end_b in matcher.get_opcodes():
        if start_b == end_b:
            continue
        value = "".join(result_words[start_b:end_b])
        highlighted = operation != "equal"
        if chunks and chunks[-1]["changed"] == highlighted:
            chunks[-1]["text"] = str(chunks[-1]["text"]) + value
        else:
            chunks.append({"text": value, "changed": highlighted})
    return chunks


def _title_case_names(text: str) -> list[str]:
    """Find multiword names we can check without a language model."""
    words = list(WORD_PATTERN.finditer(text))
    names: list[str] = []
    run: list[re.Match[str]] = []
    for word in words:
        if word.group().istitle() and (
            not run or re.fullmatch(r"[ \t]+", text[run[-1].end():word.start()])
        ):
            run.append(word)
        else:
            if len(run) > 1:
                names.append(text[run[0].start():run[-1].end()])
            run = [word] if word.group().istitle() else []
    if len(run) > 1:
        names.append(text[run[0].start():run[-1].end()])
    return names


def preserved_details(original: str, result: str) -> bool:
    """Reject drafts that drop checkable facts; users still review the meaning."""
    extractors = (NUMBER_PATTERN, IDENTIFIER_PATTERN, URL_PATTERN, EMAIL_PATTERN, QUOTE_PATTERN)
    for pattern in extractors:
        before = Counter(match.group(0).casefold() if pattern != QUOTE_PATTERN else match.group(1).casefold()
                         for match in pattern.finditer(original))
        after = Counter(match.group(0).casefold() if pattern != QUOTE_PATTERN else match.group(1).casefold()
                        for match in pattern.finditer(result))
        if any(after[detail] < count for detail, count in before.items()):
            return False
    for name, count in Counter(_title_case_names(original)).items():
        name_pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
        if len(name_pattern.findall(result)) < count:
            return False
    return True


def deep_edit(text: str, tone: str, level: str = "medium") -> str:
    from openai import OpenAI

    labels = {
        "natural": "tự nhiên, gần gũi",
        "concise": "ngắn gọn, trực tiếp",
        "professional": "chuyên nghiệp, rõ ràng",
        "academic": "học thuật, chính xác",
    }
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=45.0, max_retries=1)
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        instructions=(
            "Bạn là biên tập viên văn bản. Chỉnh sửa bản nháp bằng cùng ngôn ngữ với đầu vào. "
            f"Giọng văn mong muốn: {labels[tone]}. {LEVEL_INSTRUCTIONS[level]} "
            "Giữ nguyên từng tên riêng, mã định danh, số liệu, ngày tháng, đường dẫn, "
            "trích dẫn và các chi tiết chưa kiểm chứng. Không bỏ sót luận điểm, "
            "không đổi khẳng định hoặc mức độ chắc chắn của tác giả. "
            "Không tự thêm thông tin, không tạo nguồn trích dẫn, không giải thích quá trình. "
            "Chỉ trả về văn bản đã chỉnh sửa."
        ),
        input=text,
        max_output_tokens=7000,
        store=False,
    )
    result = response.output_text.strip()
    if not result:
        raise ValueError("Model returned an empty result")
    return result


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(deep_available=bool(os.getenv("OPENAI_API_KEY")), max_chars=MAX_CHARS)


@app.post("/api/rewrite")
def rewrite():
    if not request.is_json:
        return jsonify(error="Vui lòng gửi dữ liệu JSON."), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Dữ liệu không hợp lệ."), 400

    original = payload.get("text")
    tone = payload.get("tone", "natural")
    mode = payload.get("mode", "local")
    level = payload.get("level", "medium")
    if not isinstance(original, str) or not original.strip():
        return jsonify(error="Hãy nhập một đoạn văn trước khi chỉnh sửa."), 400
    if len(original) > MAX_CHARS:
        return jsonify(error=f"Văn bản tối đa {MAX_CHARS:,} ký tự."), 400
    if tone not in TONES or mode not in {"local", "deep"} or level not in REWRITE_LEVELS:
        return jsonify(error="Tùy chọn chỉnh sửa không hợp lệ."), 400

    if mode == "deep":
        if not os.getenv("OPENAI_API_KEY"):
            return jsonify(error="Chế độ biên tập sâu chưa được cấu hình."), 400
        try:
            result = deep_edit(original.strip(), tone, level)
            if not preserved_details(original.strip(), result):
                return jsonify(error="Bản AI đã làm mất tên riêng, số liệu hoặc trích dẫn. Hãy thử mức nhẹ hơn hoặc viết lại đoạn ngắn hơn."), 502
        except Exception:
            app.logger.exception("Deep edit failed")
            return jsonify(error="Không thể biên tập sâu lúc này. Hãy thử lại hoặc chọn chế độ cơ bản."), 502
        return jsonify(
            result=result,
            mode="deep",
            level=level,
            notes=["Đã biên tập bằng AI. Hãy đọc lại và kiểm tra các dữ kiện trước khi sử dụng."] if result != original.strip() else ["AI chưa tạo được bản khác cho đoạn này."],
            edit_count=None,
            changed=result != original.strip(),
            segments=changed_segments(original.strip(), result),
        )

    result, notes, edit_count = local_edit(original, tone)
    return jsonify(
        result=result,
        mode="local",
        notes=notes,
        edit_count=edit_count,
        changed=result != original.strip(),
        segments=changed_segments(original.strip(), result),
    )


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Dữ liệu gửi lên quá lớn."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8502")), debug=False)
