(() => {
  "use strict";

  const input = document.getElementById("input-text");
  const output = document.getElementById("output-text");
  const outputEditor = document.getElementById("output-editor");
  const tone = document.getElementById("tone-select");
  const mode = document.getElementById("mode-select");
  const level = document.getElementById("level-select");
  const levelGroup = document.getElementById("level-group");
  const editorSettings = document.querySelector(".editor-settings");
  const modeHint = document.getElementById("mode-hint");
  const inputCount = document.getElementById("input-count");
  const outputCount = document.getElementById("output-count");
  const outputStatus = document.getElementById("output-status");
  const rewriteButton = document.getElementById("rewrite-button");
  const copyButton = document.getElementById("copy-button");
  const downloadButton = document.getElementById("download-button");
  const editResultButton = document.getElementById("edit-result-button");
  const clearButton = document.getElementById("clear-button");
  const sampleButton = document.getElementById("sample-button");
  const importButton = document.getElementById("import-button");
  const importFile = document.getElementById("import-file");
  const message = document.getElementById("editor-message");
  const notesBox = document.getElementById("edit-notes");
  const notesList = document.getElementById("notes-list");
  const historyPanel = document.getElementById("history-panel");
  const historyList = document.getElementById("history-list");
  const clearHistoryButton = document.getElementById("clear-history-button");
  const emptyState = output.firstElementChild.cloneNode(true);
  const maxChars = 12000;
  let currentResult = "";
  let currentRevision = null;
  let editingResult = false;
  let revisions = [];
  let nextRevisionNumber = 0;
  let activeRequest = null;
  let deepAvailable = false;
  const levelLabels = { light: "NHẸ", medium: "VỪA", strong: "MẠNH" };
  const levelHints = {
    light: "Sửa lỗi và chỗ khó hiểu, giữ gần nguyên câu chữ.",
    medium: "Viết lại câu gượng hoặc dài, giữ thứ tự ý và giọng viết.",
    strong: "Diễn đạt lại câu và đoạn rõ rệt hơn, giữ đủ ý và dữ kiện."
  };

  document.getElementById("year").textContent = String(new Date().getFullYear());

  function wordCount(value) {
    const trimmed = value.trim();
    return trimmed ? trimmed.split(/\s+/u).length : 0;
  }

  function updateInputCount() {
    inputCount.textContent = `${wordCount(input.value).toLocaleString("vi-VN")} từ · ${input.value.length.toLocaleString("vi-VN")} / ${maxChars.toLocaleString("vi-VN")} ký tự`;
  }

  function showMessage(value, isError = true) {
    message.textContent = value;
    message.hidden = !value;
    message.classList.toggle("success", !isError);
  }

  function updateOutputCount(value) {
    outputCount.textContent = `${wordCount(value).toLocaleString("vi-VN")} từ · ${value.length.toLocaleString("vi-VN")} ký tự`;
  }

  function setResult(value, responseMode, responseLevel, notes, changed, editCount, segments, manual = false) {
    editingResult = false;
    output.hidden = false;
    outputEditor.hidden = true;
    editResultButton.textContent = "Sửa";
    if (changed === false) {
      currentResult = "";
      currentRevision = null;
      const empty = document.createElement("div");
      empty.className = "no-change-state";
      const title = document.createElement("strong");
      title.textContent = "Chưa tạo được bản chỉnh sửa khác";
      const detail = document.createElement("span");
      detail.textContent = responseMode === "deep"
        ? "Chế độ biên tập sâu chưa tạo được bản khác. Bản gốc vẫn ở ô bên trái."
        : "Chế độ cơ bản chỉ sửa những cách diễn đạt mà nó nhận diện được. Bản gốc vẫn ở ô bên trái.";
      empty.append(title, detail);
      output.replaceChildren(empty);
      outputCount.textContent = "Chưa có bản chỉnh sửa";
      outputStatus.textContent = "CHƯA CÓ THAY ĐỔI";
      outputStatus.classList.remove("ready");
      editResultButton.disabled = true;
      copyButton.disabled = true;
      downloadButton.disabled = true;
    } else {
      currentResult = value;
      output.replaceChildren();
      if (Array.isArray(segments) && segments.length) {
        for (const segment of segments) {
          if (segment.changed) {
            const mark = document.createElement("mark");
            mark.className = "edit-highlight";
            mark.title = "Phần đã chỉnh sửa";
            mark.textContent = segment.text;
            output.append(mark);
          } else {
            output.append(document.createTextNode(segment.text));
          }
        }
      } else {
        output.textContent = value;
      }
      updateOutputCount(value);
      outputStatus.textContent = manual ? "BẠN ĐÃ SỬA" : responseMode === "deep" ? `AI · ${levelLabels[responseLevel] || "VỪA"}` : `ĐÃ SỬA ${editCount} CHỖ`;
      outputStatus.classList.add("ready");
      editResultButton.disabled = false;
      copyButton.disabled = false;
      downloadButton.disabled = false;
    }
    notesList.replaceChildren();
    for (const note of notes || []) {
      const item = document.createElement("li");
      item.textContent = note;
      notesList.append(item);
    }
    notesBox.hidden = !notesList.childElementCount;
  }

  function clearResult() {
    currentResult = "";
    currentRevision = null;
    editingResult = false;
    output.hidden = false;
    outputEditor.hidden = true;
    outputEditor.value = "";
    output.replaceChildren(emptyState.cloneNode(true));
    outputCount.textContent = "Kết quả sẽ hiện ở đây";
    outputStatus.textContent = "CHỜ BẢN NHÁP";
    outputStatus.classList.remove("ready");
    editResultButton.textContent = "Sửa";
    editResultButton.disabled = true;
    copyButton.disabled = true;
    downloadButton.disabled = true;
    notesList.replaceChildren();
    notesBox.hidden = true;
    renderHistory();
  }

  function renderHistory() {
    historyList.replaceChildren();
    historyPanel.hidden = revisions.length === 0;
    for (const revision of revisions) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      if (currentRevision && currentRevision.id === revision.id) button.setAttribute("aria-current", "true");
      const title = document.createElement("strong");
      const kind = revision.manual ? "Bạn đã sửa" : revision.mode === "deep" ? `AI · ${levelLabels[revision.level] || "VỪA"}` : "Cơ bản";
      title.textContent = `Bản ${revision.id} · ${kind}`;
      const preview = document.createElement("span");
      preview.textContent = revision.result.replace(/\s+/gu, " ");
      button.append(title, preview);
      button.addEventListener("click", () => restoreRevision(revision));
      item.append(button);
      historyList.append(item);
    }
  }

  function displayRevision(revision) {
    currentRevision = revision;
    setResult(revision.result, revision.mode, revision.level, revision.notes, true, revision.edit_count, revision.segments, revision.manual);
    renderHistory();
  }

  function rememberRevision(revision) {
    const existingIndex = revisions.findIndex((saved) =>
      saved.source === revision.source && saved.result === revision.result &&
      saved.mode === revision.mode && saved.tone === revision.tone &&
      saved.level === revision.level && saved.manual === revision.manual
    );
    if (existingIndex !== -1) {
      const [existing] = revisions.splice(existingIndex, 1);
      revisions.unshift(existing);
      displayRevision(existing);
      return;
    }
    const saved = { ...revision, id: ++nextRevisionNumber };
    revisions.unshift(saved);
    revisions = revisions.slice(0, 5);
    displayRevision(saved);
  }

  function finishEditing(silent = false) {
    if (!editingResult || !currentRevision) return true;
    const edited = outputEditor.value;
    if (!edited.trim()) {
      if (!silent) {
        showMessage("Bản kết quả đang trống. Hãy nhập nội dung trước khi lưu.");
        outputEditor.focus();
      }
      return silent;
    }
    const before = currentRevision;
    if (edited !== before.result) {
      const manual = edited !== before.baseResult;
      rememberRevision({
        ...before,
        result: edited,
        manual,
        segments: manual ? null : before.baseSegments,
        notes: manual ? [...before.baseNotes, "Bạn đã chỉnh sửa bản kết quả."] : before.baseNotes
      });
    } else {
      displayRevision(before);
    }
    showMessage("");
    return true;
  }

  function restoreRevision(revision) {
    finishEditing(true);
    if (activeRequest) activeRequest.abort();
    activeRequest = null;
    rewriteButton.disabled = false;
    rewriteButton.firstChild.textContent = "Biên tập bản nháp ";
    input.value = revision.source;
    tone.value = revision.tone;
    mode.value = revision.mode;
    level.value = revision.level;
    updateInputCount();
    updateModeHint();
    displayRevision(revision);
    showMessage("");
  }

  function updateModeHint() {
    const usingAI = mode.value === "deep";
    levelGroup.hidden = !usingAI;
    editorSettings.classList.toggle("has-level", usingAI);
    modeHint.textContent = usingAI
      ? `${levelHints[level.value]} Văn bản được gửi tới API AI; hãy đọc lại kết quả.`
      : `Chế độ cơ bản dùng quy tắc có sẵn; một số đoạn có thể không thay đổi.${deepAvailable ? "" : " AI chưa được bật trên máy chủ."}`;
  }

  async function loadStatus() {
    try {
      const response = await fetch("/api/status");
      if (!response.ok) return;
      const data = await response.json();
      if (data.deep_available) {
        deepAvailable = true;
        const option = mode.querySelector('option[value="deep"]');
        option.disabled = false;
        option.textContent = "Biên tập AI";
        if (!input.value.trim() && !currentResult && !activeRequest) mode.value = "deep";
      }
      updateModeHint();
    } catch (_) {
      // The basic editor remains available if the status endpoint is unreachable.
    }
  }

  async function rewrite() {
    finishEditing(true);
    const text = input.value.trim();
    if (!text) {
      showMessage("Hãy nhập một đoạn văn trước khi biên tập.");
      input.focus();
      return;
    }
    if (text.length > maxChars) {
      showMessage("Bản nháp vượt quá 12.000 ký tự.");
      input.focus();
      return;
    }
    showMessage("");
    clearResult();
    rewriteButton.disabled = true;
    rewriteButton.firstChild.textContent = "Đang biên tập... ";
    outputStatus.textContent = "ĐANG XỬ LÝ";
    outputStatus.classList.remove("ready");
    const controller = new AbortController();
    activeRequest = controller;
    try {
      const response = await fetch("/api/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, tone: tone.value, mode: mode.value, level: level.value }),
        signal: controller.signal
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Không thể biên tập lúc này.");
      if (activeRequest === controller) {
        if (data.changed) {
          rememberRevision({
            ...data,
            source: text,
            tone: tone.value,
            level: data.level || level.value,
            baseResult: data.result,
            baseSegments: data.segments,
            baseNotes: data.notes,
            manual: false
          });
        } else {
          setResult(data.result, data.mode, data.level, data.notes, false, data.edit_count, data.segments);
        }
      }
    } catch (error) {
      if (error.name !== "AbortError" && activeRequest === controller) {
        showMessage(error.message || "Không thể kết nối. Hãy thử lại.");
        outputStatus.textContent = currentResult ? "KẾT QUẢ TRƯỚC" : "CHỜ BẢN NHÁP";
      }
    } finally {
      if (activeRequest === controller) {
        activeRequest = null;
        rewriteButton.disabled = false;
        rewriteButton.firstChild.textContent = "Biên tập bản nháp ";
      }
    }
  }

  function invalidateResult() {
    finishEditing(true);
    if (activeRequest) activeRequest.abort();
    activeRequest = null;
    rewriteButton.disabled = false;
    rewriteButton.firstChild.textContent = "Biên tập bản nháp ";
    clearResult();
    showMessage("");
  }

  async function importDraft() {
    const file = importFile.files && importFile.files[0];
    importFile.value = "";
    if (!file) return;
    if (!/\.(txt|md)$/iu.test(file.name)) {
      showMessage("Chỉ hỗ trợ tệp TXT hoặc Markdown (.md).");
      return;
    }
    if (file.size > 100000) {
      showMessage("Tệp quá lớn. Bản nháp tối đa 12.000 ký tự.");
      return;
    }
    try {
      const content = (await file.text()).replace(/^\uFEFF/u, "");
      if (!content.trim()) {
        showMessage("Tệp không có nội dung văn bản.");
        return;
      }
      if (content.length > maxChars) {
        showMessage("Tệp vượt quá 12.000 ký tự. Hãy rút gọn trước khi nhập.");
        return;
      }
      input.value = content;
      updateInputCount();
      invalidateResult();
      showMessage(`Đã nhập tệp ${file.name}.`, false);
      input.focus();
    } catch (_) {
      showMessage("Không đọc được tệp. Hãy thử một tệp TXT hoặc Markdown khác.");
    }
  }

  function toggleResultEditing() {
    if (editingResult) {
      finishEditing();
      return;
    }
    if (!currentRevision) return;
    editingResult = true;
    outputEditor.value = currentResult;
    output.hidden = true;
    outputEditor.hidden = false;
    editResultButton.textContent = "Xong";
    outputStatus.textContent = "ĐANG SỬA";
    outputStatus.classList.remove("ready");
    outputEditor.focus();
  }

  async function copyResult() {
    if (!currentResult) return;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(currentResult);
      } else {
        const helper = document.createElement("textarea");
        helper.value = currentResult;
        helper.style.position = "fixed";
        helper.style.opacity = "0";
        document.body.append(helper);
        helper.select();
        if (!document.execCommand("copy")) throw new Error("Copy failed");
        helper.remove();
      }
      const oldText = copyButton.textContent;
      copyButton.textContent = "Đã sao chép ✓";
      window.setTimeout(() => { copyButton.textContent = oldText; }, 1800);
    } catch (_) {
      showMessage("Không thể sao chép tự động. Hãy chọn văn bản và sao chép thủ công.");
    }
  }

  function downloadResult() {
    if (!currentResult) return;
    const blob = new Blob(["\ufeff", currentResult], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "ban-da-bien-tap.txt";
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  input.addEventListener("input", () => { updateInputCount(); invalidateResult(); });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (!rewriteButton.disabled) rewrite();
    }
  });
  tone.addEventListener("change", invalidateResult);
  mode.addEventListener("change", () => { invalidateResult(); updateModeHint(); });
  level.addEventListener("change", () => { invalidateResult(); updateModeHint(); });
  rewriteButton.addEventListener("click", rewrite);
  importButton.addEventListener("click", () => importFile.click());
  importFile.addEventListener("change", importDraft);
  editResultButton.addEventListener("click", toggleResultEditing);
  outputEditor.addEventListener("input", () => {
    currentResult = outputEditor.value;
    updateOutputCount(currentResult);
    copyButton.disabled = !currentResult.trim();
    downloadButton.disabled = !currentResult.trim();
    showMessage("");
  });
  copyButton.addEventListener("click", copyResult);
  downloadButton.addEventListener("click", downloadResult);
  clearHistoryButton.addEventListener("click", () => {
    revisions = [];
    renderHistory();
  });
  clearButton.addEventListener("click", () => {
    input.value = "";
    updateInputCount();
    invalidateResult();
    input.focus();
  });
  sampleButton.addEventListener("click", () => {
    input.value = "trong bối cảnh hiện nay, việc quản lý công việc đóng vai trò quan trọng đối với nhóm. Bên cạnh đó, chúng tôi cần rà soát báo cáo nhằm mục đích đưa ra quyết định một cách nhanh chóng.";
    tone.value = "concise";
    updateInputCount();
    invalidateResult();
    input.focus();
  });

  updateInputCount();
  loadStatus();
})();
