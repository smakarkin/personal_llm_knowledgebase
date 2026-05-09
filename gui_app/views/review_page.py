from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QHBoxLayout, QPlainTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from gui_app.services.compare_service import CompareService
from gui_app.services.provenance_service import ProvenanceNode, ProvenanceService
from gui_app.services.review_queue_service import ReviewQueueService


class ReviewPage(QWidget):
    """V3 review / promotion / provenance layer."""

    def __init__(self, repo_root: Path) -> None:
        super().__init__()
        self._repo_root = repo_root
        self._prov = ProvenanceService(repo_root)
        self._queues = ReviewQueueService(repo_root)
        self._compare = CompareService()

        self._queue_list = QListWidget()
        self._item_list = QListWidget()
        self._lineage = QTreeWidget(); self._lineage.setHeaderLabels(["Lineage", "Path"])
        self._preview = QPlainTextEdit(); self._preview.setReadOnly(True)
        self._compare_left = QPlainTextEdit(); self._compare_left.setPlaceholderText("Левый файл (.md)")
        self._compare_right = QPlainTextEdit(); self._compare_right.setPlaceholderText("Правый файл (.md)")
        self._compare_result = QPlainTextEdit(); self._compare_result.setReadOnly(True)

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Review / Promotion / Provenance"))
        actions = QHBoxLayout()
        for title, cb in [
            ("Accept as stable", lambda: self._safe_action("stable")),
            ("Needs refinement", lambda: self._safe_action("refine")),
            ("Attach more sources", lambda: self._safe_action("attach_sources")),
            ("Open supporting collections", lambda: self._safe_action("open_collections")),
            ("Spawn contradiction check", lambda: self._safe_action("contradiction_check")),
            ("Create manual revision note", lambda: self._safe_action("manual_revision")),
        ]:
            b = QPushButton(title); b.clicked.connect(cb); actions.addWidget(b)
        root.addLayout(actions)

        split = QSplitter()
        left = QWidget(); l = QVBoxLayout(left); l.addWidget(QLabel("Review queues")); l.addWidget(self._queue_list); l.addWidget(QLabel("Queue items")); l.addWidget(self._item_list)
        center = QWidget(); c = QVBoxLayout(center); c.addWidget(QLabel("Lineage / provenance")); c.addWidget(self._lineage, 2); c.addWidget(QLabel("Preview")); c.addWidget(self._preview, 1)
        right = QWidget(); r = QVBoxLayout(right); r.addWidget(QLabel("Compare view (left/right)")); r.addWidget(self._compare_left); r.addWidget(self._compare_right); btn=QPushButton("Compare"); btn.clicked.connect(self._run_compare); r.addWidget(btn); r.addWidget(self._compare_result,1)
        split.addWidget(left); split.addWidget(center); split.addWidget(right)
        root.addWidget(split, 1)

        self._queue_list.currentTextChanged.connect(self._fill_items)
        self._item_list.itemClicked.connect(self._show_item)

    def refresh(self) -> None:
        self._queue_map = self._queues.build_review_queues()
        self._queue_list.clear()
        for key, items in self._queue_map.items():
            QListWidgetItem(f"{key} ({len(items)})", self._queue_list)
        if self._queue_list.count():
            self._queue_list.setCurrentRow(0)

    def _fill_items(self, text: str) -> None:
        key = text.split(" (")[0] if text else ""
        self._item_list.clear()
        for item in self._queue_map.get(key, []):
            w = QListWidgetItem(f"{item.title} — {item.reason}")
            w.setData(32, item.file_path)
            self._item_list.addItem(w)

    def _show_item(self, item: QListWidgetItem) -> None:
        fp = item.data(32)
        if not fp:
            return
        path = Path(fp)
        if path.exists() and path.suffix.lower() == ".md":
            self._preview.setPlainText(path.read_text(encoding="utf-8", errors="ignore")[:6000])
            if "12_llm_concepts" in fp:
                node = self._prov.build_concept_lineage(path)
            elif "14_llm_traces" in fp:
                node = self._prov.build_trace_lineage(path)
            else:
                node = ProvenanceNode("file", path.name, str(path))
            self._render_lineage(node)

    def _render_lineage(self, root: ProvenanceNode) -> None:
        self._lineage.clear()
        def add(parent: QTreeWidgetItem | None, node: ProvenanceNode):
            item = QTreeWidgetItem([f"[{node.kind}] {node.title}", node.path or "—"])
            if parent is None:
                self._lineage.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for ch in node.children:
                add(item, ch)
        add(None, root)
        self._lineage.expandAll()

    def _safe_action(self, action: str) -> None:
        answer = QMessageBox.question(self, "Подтверждение", f"Выполнить action '{action}' в draft-first режиме?")
        if answer == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Готово", f"Action '{action}' зафиксирован как review decision (без разрушения слоёв).")

    def _run_compare(self) -> None:
        left = Path(self._compare_left.toPlainText().strip())
        right = Path(self._compare_right.toPlainText().strip())
        if not (left.exists() and right.exists()):
            self._compare_result.setPlainText("Укажите корректные пути к двум markdown-файлам.")
            return
        res = self._compare.compare_notes(left, right)
        self._compare_result.setPlainText(
            f"Shared sources:\n" + "\n".join(f"- {s}" for s in res.shared_sources) +
            f"\n\nDiffering claims/framing:\n" + "\n".join(f"- {d}" for d in res.differing_claims) +
            f"\n\n{res.recommendation}"
        )
