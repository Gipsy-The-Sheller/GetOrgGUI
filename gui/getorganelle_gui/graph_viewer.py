"""Bandage-style interactive assembly-graph viewer built on QPainter.

The canvas supports zoom/pan, node dragging, hover/selection, coverage/length/
GC colouring, labels, search and PNG export.  Nodes use a custom
QLinearGradient brush; the background is a tiled QBrush.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .graph_model import (
    AssemblyGraph,
    GraphNode,
    edge_endpoint_sides,
    layout_graph_with_ends,
    load_graph,
)
from .theme import LIGHT, Tokens
from .widgets import human_bp

COLOR_MODES = {
    "Coverage": "coverage",
    "Length": "length",
    "GC content": "gc",
    "Uniform": "uniform",
}
LABEL_MODES = {
    "None": "none",
    "Node ID": "id",
    "Length": "length",
    "Coverage": "coverage",
}

COVERAGE_STOPS = [
    (0.00, QColor("#2C7BB6")),
    (0.25, QColor("#00A6CA")),
    (0.50, QColor("#00CCBC")),
    (0.72, QColor("#90EB9D")),
    (0.88, QColor("#FFFF8C")),
    (1.00, QColor("#F9D057")),
]


def _percentile(values, fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return float(ordered[index])


class GraphCanvas(QWidget):
    node_selected = pyqtSignal(object)
    status = pyqtSignal(str)

    def __init__(self, tokens: Tokens = LIGHT, parent=None):
        super().__init__(parent)
        self.tokens = tokens
        self.graph: Optional[AssemblyGraph] = None
        self.positions: Dict[str, Tuple[float, float]] = {}
        self.ends: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = {}
        self.edge_pairs = []
        self._background: Optional[QBrush] = None
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.color_mode = "coverage"
        self.label_mode = "none"
        self.selected_id: Optional[str] = None
        self.hovered_id: Optional[str] = None
        self._drag_node: Optional[str] = None
        self._drag_start = QPointF()
        self._pan_start = QPointF()
        self._press_pos = QPointF()
        self._moved = False
        self._value_range = (0.0, 1.0)
        self._graph_center = (0.5, 0.5)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(360, 260)
        self.layout_note = ""

    # ------------------------------------------------------------------ data
    def set_tokens(self, tokens: Tokens) -> None:
        self.tokens = tokens
        self._background = None
        self.update()

    def set_graph(
        self,
        graph: AssemblyGraph,
        centers,
        ends,
        note: str = "",
    ) -> None:
        self.graph = graph
        self.positions = dict(centers)
        self.ends = dict(ends)
        if self.positions:
            self._graph_center = (
                sum(x for x, _ in self.positions.values()) / len(self.positions),
                sum(y for _, y in self.positions.values()) / len(self.positions),
            )
        else:
            self._graph_center = (0.5, 0.5)
        self.layout_note = note
        self.selected_id = None
        self.hovered_id = None
        self.edge_pairs = [
            edge
            for edge in graph.edges
            if edge.source in self.ends and edge.target in self.ends
        ]
        self._value_range = self._compute_range()
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.update()
        self._emit_status()

    def clear(self) -> None:
        self.graph = None
        self.positions = {}
        self.ends = {}
        self.edge_pairs = []
        self.selected_id = None
        self.hovered_id = None
        self._graph_center = (0.5, 0.5)
        self.update()
        self.status.emit("")

    def _compute_range(self) -> Tuple[float, float]:
        if self.graph is None:
            return 0.0, 1.0
        values = []
        for node in self.graph.nodes.values():
            value = self._value_for(node)
            if value > 0:
                values.append(value)
        if not values:
            return 0.0, 1.0
        low = _percentile(values, 0.05)
        high = _percentile(values, 0.95)
        if high <= low:
            high = low + 1.0
        return low, high

    def _value_for(self, node: GraphNode) -> float:
        if self.color_mode == "length":
            return float(node.length)
        if self.color_mode == "gc":
            return float(node.gc)
        if self.color_mode == "uniform":
            return 1.0
        return float(node.coverage)

    def _color_for(self, node: GraphNode) -> QColor:
        if self.color_mode == "uniform":
            return QColor(self.tokens.primary)
        value = self._value_for(node)
        low, high = self._value_range
        fraction = (value - low) / (high - low) if high > low else 0.5
        fraction = min(1.0, max(0.0, fraction))
        for index in range(1, len(COVERAGE_STOPS)):
            left_pos, left_color = COVERAGE_STOPS[index - 1]
            right_pos, right_color = COVERAGE_STOPS[index]
            if fraction <= right_pos:
                span = right_pos - left_pos if right_pos > left_pos else 1.0
                local = (fraction - left_pos) / span
                return QColor(
                    int(left_color.red() + (right_color.red() - left_color.red()) * local),
                    int(left_color.green() + (right_color.green() - left_color.green()) * local),
                    int(left_color.blue() + (right_color.blue() - left_color.blue()) * local),
                )
        return QColor(COVERAGE_STOPS[-1][1])

    # -------------------------------------------------------------- transform
    def _base_scale(self) -> float:
        return max(40.0, min(self.width(), self.height()) * 0.86)

    def _to_screen(self, x: float, y: float) -> QPointF:
        base = self._base_scale() * self.zoom
        return QPointF(
            self.width() / 2 + self.pan.x() + (x - 0.5) * base,
            self.height() / 2 + self.pan.y() + (y - 0.5) * base,
        )

    def _from_screen(self, point: QPointF) -> QPointF:
        base = self._base_scale() * self.zoom
        return QPointF(
            (point.x() - self.width() / 2 - self.pan.x()) / base + 0.5,
            (point.y() - self.height() / 2 - self.pan.y()) / base + 0.5,
        )

    def _node_thickness(self, node: GraphNode) -> float:
        low, high = self._value_range
        norm = 0.5
        if high > low:
            norm = min(1.0, max(0.0, (node.coverage - low) / (high - low)))
        scale = min(2.2, max(0.7, self.zoom ** 0.25))
        return min(22.0, max(4.0, (6.0 + 10.0 * norm) * scale))

    def _node_path_points(self, node_id: str) -> List[QPointF]:
        """Sample a bent, multi-segment path between the node's two ends."""
        if node_id not in self.ends:
            return []
        start_world, end_world = self.ends[node_id]
        mid_world = (
            (start_world[0] + end_world[0]) / 2.0,
            (start_world[1] + end_world[1]) / 2.0,
        )
        centre = getattr(self, "_graph_center", (0.5, 0.5))
        outward = (mid_world[0] - centre[0], mid_world[1] - centre[1])
        length = math.hypot(outward[0], outward[1])
        dx = end_world[0] - start_world[0]
        dy = end_world[1] - start_world[1]
        span = math.hypot(dx, dy)
        if length < 1e-6:
            # Perpendicular to the node, deterministic sign.
            sign = 1.0 if (hash(node_id) & 1) else -1.0
            outward = (-dy / span * sign if span else 0.0, dx / span * sign if span else 1.0)
            length = 1.0
        bend = 0.20 * span
        control_world = (
            mid_world[0] + outward[0] / length * bend,
            mid_world[1] + outward[1] / length * bend,
        )
        points: List[QPointF] = []
        segments = 6
        for step in range(segments + 1):
            t = step / segments
            x = (1 - t) ** 2 * start_world[0] + 2 * (1 - t) * t * control_world[0] + t * t * end_world[0]
            y = (1 - t) ** 2 * start_world[1] + 2 * (1 - t) * t * control_world[1] + t * t * end_world[1]
            points.append(self._to_screen(x, y))
        return points

    @staticmethod
    def _point_segment_distance(point: QPointF, start: QPointF, end: QPointF) -> float:
        vx, vy = end.x() - start.x(), end.y() - start.y()
        wx, wy = point.x() - start.x(), point.y() - start.y()
        length_sq = vx * vx + vy * vy
        if length_sq <= 1e-9:
            return math.hypot(wx, wy)
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / length_sq))
        return math.hypot(point.x() - (start.x() + t * vx), point.y() - (start.y() + t * vy))

    def _edge_endpoints(self, edge) -> Tuple[QPointF, QPointF]:
        source_side, target_side = edge_endpoint_sides(self.graph, edge)
        source = self.ends[edge.source][source_side]
        target = self.ends[edge.target][target_side]
        return self._to_screen(*source), self._to_screen(*target)

    def _background_brush(self) -> QBrush:
        if self._background is not None:
            return self._background
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        dot = QColor(self.tokens.outline)
        dot.setAlpha(120)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(dot))
        painter.drawEllipse(QPointF(9, 9), 1.0, 1.0)
        painter.end()
        self._background = QBrush(pixmap)
        return self._background

    # --------------------------------------------------------------- painting
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(self.tokens.surface_sunken))
        painter.fillRect(self.rect(), self._background_brush())
        if self.graph is None or not self.positions:
            painter.setPen(QColor(self.tokens.text_secondary))
            painter.drawText(self.rect(), Qt.AlignCenter, "No assembly graph loaded")
            painter.end()
            return
        self._draw_edges(painter)
        self._draw_nodes(painter)
        self._draw_legend(painter)
        painter.end()

    def _draw_edges(self, painter: QPainter) -> None:
        assert self.graph is not None
        selected = self.selected_id
        for edge in self.edge_pairs:
            if edge.source not in self.ends or edge.target not in self.ends:
                continue
            start, end = self._edge_endpoints(edge)
            if math.hypot(end.x() - start.x(), end.y() - start.y()) < 1:
                continue
            highlighted = selected and selected in (edge.source, edge.target)
            color = QColor(self.tokens.outline_strong)
            if highlighted:
                color = QColor(self.tokens.primary)
            color.setAlpha(180 if highlighted else 120)
            pen = QPen(color, 1.9 if highlighted else 1.25)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(start, end)
            self._draw_arrow(painter, start, end, color)

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF, color: QColor) -> None:
        vector = end - start
        length = math.hypot(vector.x(), vector.y())
        if length < 14:
            return
        unit = QPointF(vector.x() / length, vector.y() / length)
        normal = QPointF(-unit.y(), unit.x())
        tip = end
        back = tip - unit * 7
        arrow = QPainterPath(tip)
        arrow.lineTo(back + normal * 3.5)
        arrow.lineTo(back - normal * 3.5)
        arrow.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(arrow)

    def _draw_nodes(self, painter: QPainter) -> None:
        assert self.graph is not None
        label_requests: List[Tuple[GraphNode, List[QPointF], float]] = []
        for node_id, node in self.graph.nodes.items():
            points = self._node_path_points(node_id)
            if len(points) < 2:
                continue
            thickness = self._node_thickness(node)
            left = min(point.x() for point in points) - thickness
            right = max(point.x() for point in points) + thickness
            top = min(point.y() for point in points) - thickness
            bottom = max(point.y() for point in points) + thickness
            bounds = QRectF(left, top, right - left, bottom - top)
            if not self.rect().intersects(bounds.toAlignedRect()):
                continue
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)

            color = self._color_for(node)
            selected = node_id == self.selected_id
            hovered = node_id == self.hovered_id

            # Soft drop shadow, then a wide glow for the selected node.
            painter.save()
            painter.translate(1.6, 2.2)
            shadow = QPen(QColor(0, 0, 0, 42), thickness + 2.5)
            shadow.setCapStyle(Qt.RoundCap)
            shadow.setJoinStyle(Qt.RoundJoin)
            painter.setPen(shadow)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            painter.restore()
            if selected:
                glow_color = QColor(self.tokens.primary)
                glow_color.setAlpha(58)
                glow = QPen(glow_color, thickness + 10.0)
                glow.setCapStyle(Qt.RoundCap)
                glow.setJoinStyle(Qt.RoundJoin)
                painter.setPen(glow)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)

            border = QColor(self.tokens.primary if (selected or hovered) else self.tokens.outline_strong)
            border.setAlpha(230 if (selected or hovered) else 180)
            outline = QPen(border, thickness + 2.6)
            outline.setCapStyle(Qt.RoundCap)
            outline.setJoinStyle(Qt.RoundJoin)
            painter.setPen(outline)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

            gradient = QLinearGradient(points[0], points[-1])
            gradient.setColorAt(0.0, QColor(color).lighter(132))
            gradient.setColorAt(0.55, QColor(color))
            gradient.setColorAt(1.0, QColor(color).darker(116))
            tube = QPen()
            tube.setBrush(QBrush(gradient))
            tube.setWidthF(thickness)
            tube.setCapStyle(Qt.RoundCap)
            tube.setJoinStyle(Qt.RoundJoin)
            painter.setPen(tube)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

            # A narrow offset highlight reads as a cylindrical tube.
            vector = points[-1] - points[0]
            span = math.hypot(vector.x(), vector.y())
            if span > 2 and thickness >= 7:
                offset = QPointF(
                    -vector.y() / span * thickness * 0.16,
                    vector.x() / span * thickness * 0.16,
                )
                painter.save()
                painter.translate(offset)
                sheen = QPen(QColor(255, 255, 255, 55), max(1.0, thickness * 0.16))
                sheen.setCapStyle(Qt.RoundCap)
                sheen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(sheen)
                painter.drawPath(path)
                painter.restore()

            if self.label_mode != "none":
                label_requests.append((node, points, thickness))
        self._draw_labels(painter, label_requests)

    def _draw_legend(self, painter: QPainter) -> None:
        if self.color_mode == "uniform":
            return
        low, high = self._value_range
        if self.color_mode == "length":
            title = f"Length  {human_bp(int(low))} – {human_bp(int(high))}"
        elif self.color_mode == "gc":
            title = f"GC  {low:.1f} – {high:.1f}%"
        else:
            title = f"Coverage  {low:.1f} – {high:.1f}×"
        font = QFont(self.font())
        font.setPointSizeF(7.5)
        metrics = QFontMetricsF(font)
        width = max(190.0, metrics.horizontalAdvance(title) + 24)
        height = 34
        left = max(8, self.width() - width - 10)
        top = max(8, self.height() - height - 10)
        box = QRectF(left, top, width, height)
        surface = QColor(self.tokens.surface_alt)
        surface.setAlpha(225)
        painter.setPen(QPen(QColor(self.tokens.outline), 1))
        painter.setBrush(QBrush(surface))
        painter.drawRoundedRect(box, 5, 5)
        gradient = QLinearGradient(left + 8, 0, left + width - 8, 0)
        for position, color in COVERAGE_STOPS:
            gradient.setColorAt(position, color)
        bar = QRectF(left + 8, top + 17, width - 16, 7)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(bar, 3, 3)
        painter.setPen(QColor(self.tokens.text_secondary))
        painter.setFont(font)
        painter.drawText(QRectF(left + 8, top + 2, width - 16, 14), Qt.AlignLeft | Qt.AlignVCenter, title)

    def _draw_labels(
        self,
        painter: QPainter,
        requests: List[Tuple[GraphNode, List[QPointF], float]],
    ) -> None:
        placed: List[QRectF] = []
        for node, points, thickness in requests:
            self._draw_label(painter, node, points, thickness, placed)

    def _draw_label(
        self,
        painter: QPainter,
        node: GraphNode,
        points: List[QPointF],
        thickness: float,
        placed: List[QRectF],
    ) -> None:
        if self.label_mode == "id":
            text = node.id
        elif self.label_mode == "coverage":
            text = f"{node.coverage:.1f}×"
        else:
            text = human_bp(node.length)
        font = QFont(self.font())
        font.setPointSizeF(max(6.5, min(9.0, 7.0 * self.zoom ** 0.2)))
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(text) + 10
        height = metrics.height() + 2
        candidates = []
        for fraction in (0.5, 0.34, 0.66, 0.2, 0.8):
            index = min(
                len(points) - 1,
                max(0, int(round(fraction * (len(points) - 1)))),
            )
            anchor = points[index]
            for candidate_y in (
                anchor.y() + thickness / 2 + 3,
                anchor.y() - thickness / 2 - 3 - height,
            ):
                x = min(
                    max(4.0, anchor.x() - width / 2),
                    max(4.0, self.width() - width - 4),
                )
                candidate_y = min(
                    max(4.0, candidate_y),
                    max(4.0, self.height() - height - 4),
                )
                candidates.append(QRectF(x, candidate_y, width, height))
        box = None
        for candidate in candidates:
            padded = candidate.adjusted(-2, -2, 2, 2)
            if not any(padded.intersects(other) for other in placed):
                box = candidate
                break
        if box is None:
            return
        placed.append(box)
        surface = QColor(self.tokens.surface_alt)
        surface.setAlpha(230)
        painter.setPen(QPen(QColor(self.tokens.outline), 0.8))
        painter.setBrush(QBrush(surface))
        painter.drawRoundedRect(box, 3, 3)
        painter.setPen(QColor(self.tokens.text))
        painter.drawText(box, Qt.AlignCenter, text)

    # ------------------------------------------------------------ interaction
    def _node_at(self, point: QPointF) -> Optional[str]:
        if self.graph is None:
            return None
        for node_id in reversed(list(self.graph.nodes)):
            points = self._node_path_points(node_id)
            if len(points) < 2:
                continue
            threshold = self._node_thickness(self.graph.nodes[node_id]) / 2 + 3.0
            for start, end in zip(points, points[1:]):
                if self._point_segment_distance(point, start, end) <= threshold:
                    return node_id
        return None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus()
        self._press_pos = QPointF(event.pos())
        self._moved = False
        node_id = self._node_at(QPointF(event.pos())) if event.button() == Qt.LeftButton else None
        if node_id is not None:
            self._drag_node = node_id
            self.selected_id = node_id
            self._select(node_id)
        else:
            self._drag_node = None
            self._pan_start = QPointF(event.pos())
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        point = QPointF(event.pos())
        if (point - self._press_pos).manhattanLength() > 3:
            self._moved = True
        if event.buttons() & Qt.LeftButton:
            if self._drag_node and self._drag_node in self.positions:
                world = self._from_screen(point)
                node_id = self._drag_node
                old_x, old_y = self.positions[node_id]
                dx, dy = world.x() - old_x, world.y() - old_y
                self.positions[node_id] = (world.x(), world.y())
                if node_id in self.ends:
                    start, end = self.ends[node_id]
                    self.ends[node_id] = (
                        (start[0] + dx, start[1] + dy),
                        (end[0] + dx, end[1] + dy),
                    )
                self.update()
                return
            delta = point - self._pan_start
            self._pan_start = point
            self.pan += delta
            self.update()
            return
        node_id = self._node_at(point)
        if node_id != self.hovered_id:
            self.hovered_id = node_id
            self.update()
        if node_id is not None and self.graph is not None:
            node = self.graph.nodes[node_id]
            QToolTipText = (
                f"{node.id}\n{human_bp(node.length)} · coverage {node.coverage:.1f}×"
                + (f" · GC {node.gc:.1f}%" if node.gc else "")
            )
            from PyQt5.QtWidgets import QToolTip

            QToolTip.showText(event.globalPos(), QToolTipText, self)
        else:
            from PyQt5.QtWidgets import QToolTip

            QToolTip.hideText()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and not self._moved:
            node_id = self._node_at(QPointF(event.pos()))
            if node_id is not None:
                self.selected_id = node_id
                self._select(node_id)
        self._drag_node = None
        self.update()

    def _select(self, node_id: str) -> None:
        if self.graph is None or node_id not in self.graph.nodes:
            return
        node = self.graph.nodes[node_id]
        self.node_selected.emit(
            {
                "id": node.id,
                "length": node.length,
                "coverage": node.coverage,
                "gc": node.gc,
                "sequence": node.sequence,
                "support": node.support,
                "metadata": node.metadata,
            }
        )
        self._emit_status()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.graph is None:
            return
        cursor = QPointF(event.pos())
        before = self._from_screen(cursor)
        factor = 1.18 ** (event.angleDelta().y() / 120.0)
        self.zoom = min(12.0, max(0.15, self.zoom * factor))
        after = self._from_screen(cursor)
        # Keep the world point under the cursor fixed.
        base = self._base_scale() * self.zoom
        self.pan += QPointF((after.x() - before.x()) * base, (after.y() - before.y()) * base)
        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom = min(12.0, self.zoom * 1.2)
            self.update()
        elif event.key() == Qt.Key_Minus:
            self.zoom = max(0.15, self.zoom / 1.2)
            self.update()
        elif event.key() == Qt.Key_0:
            self.fit()
        elif event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 24
            if event.key() == Qt.Key_Left:
                self.pan -= QPointF(step, 0)
            elif event.key() == Qt.Key_Right:
                self.pan += QPointF(step, 0)
            elif event.key() == Qt.Key_Up:
                self.pan -= QPointF(0, step)
            else:
                self.pan += QPointF(0, step)
            self.update()
        else:
            super().keyPressEvent(event)

    def fit(self) -> None:
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.update()

    def focus_node(self, query: str) -> Optional[str]:
        if self.graph is None or not query:
            return None
        lowered = query.lower()
        matches = [
            node_id for node_id in self.graph.nodes if lowered in node_id.lower()
        ]
        if not matches:
            self.status.emit(f"No node matches “{query}”.")
            return None
        node_id = matches[0]
        self.selected_id = node_id
        self._select(node_id)
        if node_id in self.positions:
            x, y = self.positions[node_id]
            self.pan = QPointF()
            base = self._base_scale() * self.zoom
            self.pan = QPointF(
                -(x - 0.5) * base,
                -(y - 0.5) * base,
            )
        self.update()
        return node_id

    def _emit_status(self) -> None:
        if self.graph is None:
            self.status.emit("")
            return
        stats = self.graph.stats()
        selected = ""
        if self.selected_id and self.selected_id in self.graph.nodes:
            node = self.graph.nodes[self.selected_id]
            selected = (
                f" · selected {node.id}: {human_bp(node.length)}, "
                f"coverage {node.coverage:.1f}×"
            )
        self.status.emit(
            f"{stats['nodes']} nodes · {stats['edges']} edges · "
            f"{human_bp(stats['total_bp'])} · {stats['components']} component(s)"
            + selected
        )


class GraphViewer(QWidget):
    """Toolbar + canvas + status line."""

    def __init__(self, tokens: Tokens = LIGHT, parent=None):
        super().__init__(parent)
        self.tokens = tokens
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        toolbar = QGridLayout()
        toolbar.setSpacing(4)
        self.fit_button = QPushButton("Fit")
        self.fit_button.setToolTip("Fit graph to the canvas (0)")
        self.relayout_button = QPushButton("Re-layout")
        self.relayout_button.setToolTip("Recompute the force-directed layout")
        self.color_combo = QComboBox()
        for label, key in COLOR_MODES.items():
            self.color_combo.addItem(label, key)
        self.label_combo = QComboBox()
        for label, key in LABEL_MODES.items():
            self.label_combo.addItem(label, key)
        self.label_combo.setCurrentIndex(0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find node…")
        self.search_edit.setMaximumWidth(160)
        self.export_button = QPushButton("Export PNG")
        self.color_combo.setMaximumWidth(112)
        self.label_combo.setMaximumWidth(104)
        self.search_edit.setMaximumWidth(150)
        self.fit_button.setToolTip("Fit graph to the canvas (0)")
        toolbar.addWidget(self.fit_button, 0, 0)
        toolbar.addWidget(self.relayout_button, 0, 1)
        toolbar.addWidget(self.export_button, 0, 2)
        toolbar.addWidget(QLabel("Colour"), 1, 0)
        toolbar.addWidget(self.color_combo, 1, 1)
        toolbar.addWidget(QLabel("Label"), 1, 2)
        toolbar.addWidget(self.label_combo, 1, 3)
        toolbar.addWidget(self.search_edit, 1, 4)
        toolbar.setColumnStretch(5, 1)
        layout.addLayout(toolbar)
        self.canvas = GraphCanvas(tokens)
        layout.addWidget(self.canvas, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self._seed = 7
        self._graph: Optional[AssemblyGraph] = None
        self._cache: dict = {}

        self.fit_button.clicked.connect(self.canvas.fit)
        self.relayout_button.clicked.connect(self.relayout)
        self.color_combo.currentIndexChanged.connect(self._color_changed)
        self.label_combo.currentIndexChanged.connect(self._label_changed)
        self.search_edit.returnPressed.connect(self._search)
        self.export_button.clicked.connect(self.export_png)
        self.canvas.status.connect(self.status_label.setText)

    def set_tokens(self, tokens: Tokens) -> None:
        self.tokens = tokens
        self.canvas.set_tokens(tokens)

    def load_file(self, path: str) -> Tuple[bool, str]:
        try:
            stat = Path(path).stat()
            cache_key = (path, stat.st_mtime_ns, stat.st_size)
        except OSError:
            cache_key = None
        cached = self._cache.get(cache_key) if cache_key else None
        if cached is not None:
            graph, centers, ends, note = cached
            self._graph = graph
            self.canvas.set_graph(graph, centers, ends, note)
            self.status_label.setText(note)
            return True, note
        try:
            graph = load_graph(path)
        except (OSError, ValueError) as exc:
            self.clear()
            self.status_label.setText(str(exc))
            return False, str(exc)
        if not graph.nodes:
            self.clear()
            message = "No segments found in this graph file."
            self.status_label.setText(message)
            return False, message
        self._graph = graph
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QApplication.processEvents()
            centers, ends, note = layout_graph_with_ends(graph, seed=self._seed)
        finally:
            QApplication.restoreOverrideCursor()
        self.canvas.set_graph(graph, centers, ends, note)
        if cache_key is not None:
            self._cache[cache_key] = (graph, centers, ends, note)
        self.status_label.setText(note)
        return True, note

    def set_graph(self, graph: AssemblyGraph, note: str = "", seed: int = 7) -> None:
        self._graph = graph
        centers, ends, layout_note = layout_graph_with_ends(graph, seed=seed)
        self.canvas.set_graph(graph, centers, ends, layout_note)
        self.status_label.setText((note + " · " if note else "") + layout_note)

    def clear(self) -> None:
        self._graph = None
        self.canvas.clear()
        self.status_label.clear()

    def relayout(self) -> None:
        if self._graph is None:
            return
        self._seed += 1
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QApplication.processEvents()
            centers, ends, note = layout_graph_with_ends(self._graph, seed=self._seed)
        finally:
            QApplication.restoreOverrideCursor()
        self.canvas.set_graph(self._graph, centers, ends, note)
        self.status_label.setText(note)

    def _color_changed(self) -> None:
        self.canvas.color_mode = self.color_combo.currentData() or "coverage"
        self.canvas._value_range = self.canvas._compute_range()
        self.canvas.update()

    def _label_changed(self) -> None:
        self.canvas.label_mode = self.label_combo.currentData() or "length"
        self.canvas.update()

    def _search(self) -> None:
        self.canvas.focus_node(self.search_edit.text().strip())

    def export_png(self) -> None:
        if self._graph is None:
            return
        suggested = (Path(self._graph.path).stem if self._graph.path else "assembly_graph") + ".png"
        path, _ = QFileDialog.getSaveFileName(self, "Export graph image", suggested, "PNG image (*.png)")
        if path:
            self.canvas.grab().save(path, "PNG")


class GraphViewerDialog(QWidget):
    """Non-modal large viewer window."""

    def __init__(self, path: str, tokens: Tokens, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(f"Assembly graph · {Path(path).name}")
        self.resize(1120, 780)
        self.setWindowFlag(Qt.Window, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.viewer = GraphViewer(tokens)
        layout.addWidget(self.viewer)
        self.viewer.load_file(path)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
