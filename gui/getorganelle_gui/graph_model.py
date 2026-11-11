"""Assembly-graph parsing and layout (no Qt imports).

Supports the two formats GetOrganelle emits: GFA 1.x (S/L lines) and
SPAdes-style FASTG.  The layout is a small vectorized Fruchterman–Reingold
implementation with a deterministic initial state; large graphs fall back to a
circular layout so the UI stays responsive.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

FASTG_HEADER = re.compile(r"_length_(\d+)(?:_cov_([0-9.]+))?")
GFA_TAG = re.compile(r"^([A-Za-z][A-Za-z0-9]):([AifZJHB]):(.*)$")


@dataclass
class GraphNode:
    id: str
    length: int = 0
    coverage: float = 0.0
    sequence: str = ""
    gc: float = 0.0
    support: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def short_label(self) -> str:
        return self.id


@dataclass
class GraphEdge:
    source: str
    target: str
    source_reverse: bool = False
    target_reverse: bool = False
    overlap: str = ""


@dataclass
class AssemblyGraph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    path: str = ""
    format: str = ""

    def add_node(self, node: GraphNode) -> None:
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            return
        # FASTG contains both a node and its reverse-complement record.
        if not existing.sequence and node.sequence:
            existing.sequence = node.sequence
        if not existing.length and node.length:
            existing.length = node.length
        if not existing.coverage and node.coverage:
            existing.coverage = node.coverage

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source == edge.target:
            return
        self.edges.append(edge)

    @property
    def total_bp(self) -> int:
        return sum(node.length for node in self.nodes.values())

    def components(self) -> int:
        parent = {node_id: node_id for node_id in self.nodes}

        def find(item: str) -> str:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        for edge in self.edges:
            if edge.source in parent and edge.target in parent:
                ra, rb = find(edge.source), find(edge.target)
                if ra != rb:
                    parent[rb] = ra
        return len({find(node_id) for node_id in parent})

    def dead_ends(self) -> int:
        degree = {node_id: 0 for node_id in self.nodes}
        for edge in self.edges:
            if edge.source in degree:
                degree[edge.source] += 1
            if edge.target in degree:
                degree[edge.target] += 1
        return sum(1 for value in degree.values() if value == 1)

    def n50(self) -> int:
        lengths = sorted((node.length for node in self.nodes.values() if node.length), reverse=True)
        if not lengths:
            return 0
        half = sum(lengths) / 2.0
        running = 0
        for length in lengths:
            running += length
            if running >= half:
                return length
        return lengths[-1]

    def stats(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "total_bp": self.total_bp,
            "components": self.components(),
            "dead_ends": self.dead_ends(),
            "n50": self.n50(),
        }


def _gc(sequence: str) -> float:
    if not sequence:
        return 0.0
    sequence = sequence.upper()
    gc = sequence.count("G") + sequence.count("C")
    return round(100.0 * gc / len(sequence), 2)


def _parse_tags(fields: Iterable[str]) -> Dict[str, str]:
    tags = {}
    for field in fields:
        match = GFA_TAG.match(field)
        if match:
            tags[match.group(1)] = match.group(3)
    return tags


def parse_gfa(text: str, path: str = "") -> AssemblyGraph:
    graph = AssemblyGraph(path=path, format="GFA")
    for raw_line in text.splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.rstrip("\n").split("\t")
        record = fields[0]
        if record == "S" and len(fields) >= 3:
            node_id = fields[1]
            sequence = "" if fields[2] == "*" else fields[2]
            tags = _parse_tags(fields[3:])
            length = int(tags.get("LN", len(sequence)) or len(sequence))
            support = float(tags.get("RC", 0) or 0)
            coverage = tags.get("cov") or tags.get("dp")
            if coverage is not None:
                try:
                    coverage_value = float(coverage)
                except ValueError:
                    coverage_value = 0.0
            elif support and length:
                coverage_value = support / length
            else:
                coverage_value = 0.0
            graph.add_node(
                GraphNode(
                    id=node_id,
                    length=length,
                    coverage=coverage_value,
                    sequence=sequence,
                    gc=_gc(sequence),
                    support=support,
                    metadata=tags,
                )
            )
        elif record == "L" and len(fields) >= 6:
            graph.add_edge(
                GraphEdge(
                    source=fields[1],
                    target=fields[3],
                    source_reverse=fields[2] == "-",
                    target_reverse=fields[4] == "-",
                    overlap=fields[5],
                )
            )
    return graph


def parse_fastg(text: str, path: str = "") -> AssemblyGraph:
    graph = AssemblyGraph(path=path, format="FASTG")
    current_id: Optional[str] = None
    current_seq: List[str] = []
    seen_edges = set()

    def flush() -> None:
        nonlocal current_id, current_seq
        if current_id is None:
            return
        sequence = "".join(current_seq)
        node = graph.nodes.get(current_id)
        if node is not None:
            if not node.sequence and sequence:
                node.sequence = sequence
                node.gc = _gc(sequence)
            if not node.length:
                node.length = len(sequence)
        current_id = None
        current_seq = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            flush()
            header = line[1:]
            body = header.rstrip(";")
            node_part, _, links_part = body.partition(":")
            node_part = node_part.strip()
            current_id = node_part.rstrip("'")
            match = FASTG_HEADER.search(node_part)
            length = int(match.group(1)) if match else 0
            coverage = float(match.group(2)) if match and match.group(2) else 0.0
            graph.add_node(
                GraphNode(
                    id=current_id,
                    length=length,
                    coverage=coverage,
                    support=coverage,
                )
            )
            if links_part and not node_part.endswith("'"):
                for link in links_part.split(","):
                    link = link.strip().rstrip(";")
                    if not link:
                        continue
                    target_reverse = link.endswith("'")
                    target = link.rstrip("'")
                    if not target:
                        continue
                    if target not in graph.nodes:
                        graph.add_node(GraphNode(id=target))
                    key = tuple(sorted((current_id, target)))
                    if key in seen_edges:
                        continue
                    seen_edges.add(key)
                    graph.add_edge(
                        GraphEdge(
                            source=current_id,
                            target=target,
                            target_reverse=target_reverse,
                        )
                    )
        else:
            current_seq.append(line)
    flush()
    return graph


def load_graph(path: str, max_bytes: int = 80 * 1024 * 1024) -> AssemblyGraph:
    file_path = Path(path)
    size = file_path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"Graph file is {size / 1024 / 1024:.0f} MB; the in-app viewer supports up to "
            f"{max_bytes // 1024 // 1024} MB. Open it in Bandage instead."
        )
    text = file_path.read_text(encoding="utf-8", errors="replace")
    suffix = file_path.suffix.lower()
    if suffix == ".gfa":
        graph = parse_gfa(text, str(file_path))
    elif suffix == ".fastg":
        graph = parse_fastg(text, str(file_path))
    else:
        # Sniff a few lines when the suffix is unusual.
        if any(line.startswith(("S\t", "L\t")) for line in text.splitlines()[:50]):
            graph = parse_gfa(text, str(file_path))
        else:
            graph = parse_fastg(text, str(file_path))
    return graph


def _node_components(graph: AssemblyGraph) -> List[List[str]]:
    parent = {node_id: node_id for node_id in graph.nodes}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for edge in graph.edges:
        if edge.source in parent and edge.target in parent:
            ra, rb = find(edge.source), find(edge.target)
            if ra != rb:
                parent[rb] = ra
    groups: Dict[str, List[str]] = {}
    for node_id in graph.nodes:
        groups.setdefault(find(node_id), []).append(node_id)
    return list(groups.values())


def _separate_components(
    graph: AssemblyGraph, positions
) -> None:
    components = _node_components(graph)
    if len(components) < 2 or len(components) > 64:
        return
    import math

    cols = max(1, int(math.ceil(math.sqrt(len(components)))))
    rows = max(1, int(math.ceil(len(components) / cols)))
    components.sort(key=lambda item: (-len(item), item[0]))
    for index, members in enumerate(components):
        target_x = (index % cols + 0.5) / cols
        target_y = (index // cols + 0.5) / rows
        xs = [positions[node_id][0] for node_id in members]
        ys = [positions[node_id][1] for node_id in members]
        dx = target_x - sum(xs) / len(xs)
        dy = target_y - sum(ys) / len(ys)
        for node_id in members:
            x, y = positions[node_id]
            positions[node_id] = (x + dx, y + dy)


def _circular_layout(graph: AssemblyGraph) -> Dict[str, Tuple[float, float]]:
    ids = list(graph.nodes)
    positions: Dict[str, Tuple[float, float]] = {}
    if not ids:
        return positions
    if len(ids) == 1:
        return {ids[0]: (0.5, 0.5)}
    # Keep disconnected components together by ordering on the component id.
    order = {node_id: index for index, node_id in enumerate(ids)}
    angles = [2 * math.pi * order[node_id] / len(ids) for node_id in ids]
    for node_id, angle in zip(ids, angles):
        positions[node_id] = (0.5 + 0.44 * math.cos(angle), 0.5 + 0.44 * math.sin(angle))
    return positions


def layout_graph(
    graph: AssemblyGraph,
    *,
    seed: int = 7,
    max_force_nodes: int = 800,
) -> Tuple[Dict[str, Tuple[float, float]], str]:
    """Return normalized positions plus a human-readable layout note."""
    ids = list(graph.nodes)
    count = len(ids)
    if count == 0:
        return {}, "empty graph"
    if count == 1:
        return {ids[0]: (0.5, 0.5)}, "single node"
    if count > max_force_nodes:
        return _circular_layout(graph), (
            f"{count} nodes: circular layout (drag nodes; force layout is limited to "
            f"{max_force_nodes})"
        )
    try:
        import numpy as np
    except ImportError:
        return _circular_layout(graph), "numpy not found: circular layout"

    index = {node_id: i for i, node_id in enumerate(ids)}
    rng = np.random.default_rng(seed)
    angles = np.linspace(0, 2 * math.pi, count, endpoint=False)
    radius = 0.42 + 0.02 * min(count, 10)
    positions = np.column_stack(
        [0.5 + radius * np.cos(angles), 0.5 + radius * np.sin(angles)]
    )
    positions += rng.normal(scale=0.01, size=positions.shape)

    edge_pairs = [
        (index[edge.source], index[edge.target])
        for edge in graph.edges
        if edge.source in index and edge.target in index
    ]
    if edge_pairs:
        edge_array = np.asarray(edge_pairs, dtype=np.int32)
    else:
        edge_array = np.zeros((0, 2), dtype=np.int32)

    iterations = 320 if count <= 250 else 220 if count <= 500 else 80
    area = 1.0
    k = math.sqrt(area / count)
    temperature = 0.10
    for iteration in range(iterations):
        delta = positions[:, None, :] - positions[None, :, :]
        distance = np.sqrt(np.sum(delta * delta, axis=2)) + 1e-6
        # Repulsion: k^2 / d, applied along the normalized difference.
        magnitude = (k * k) / (distance * distance)
        np.fill_diagonal(magnitude, 0.0)
        displacement = np.einsum("ij,ijk->ik", magnitude, delta)
        if len(edge_array):
            source = positions[edge_array[:, 0]]
            target = positions[edge_array[:, 1]]
            vector = target - source
            length = np.sqrt(np.sum(vector * vector, axis=1)) + 1e-6
            force = (length * length / k)[:, None] * (vector / length[:, None])
            np.add.at(displacement, edge_array[:, 0], force)
            np.add.at(displacement, edge_array[:, 1], -force)
        disp_len = np.sqrt(np.sum(displacement * displacement, axis=1)) + 1e-9
        step = np.minimum(disp_len, temperature)[:, None] * displacement / disp_len[:, None]
        positions += step
        temperature *= 0.992
        # Keep the layout centered.
        positions -= positions.mean(axis=0)

    result_positions = {
        node_id: (float(positions[i, 0]), float(positions[i, 1]))
        for i, node_id in enumerate(ids)
    }
    _separate_components(graph, result_positions)
    positions = np.asarray([result_positions[node_id] for node_id in ids], dtype=float)
    minimum = positions.min(axis=0)
    maximum = positions.max(axis=0)
    span = np.maximum(maximum - minimum, 1e-6)
    positions = (positions - minimum) / span
    positions = 0.04 + positions * 0.92
    result = {node_id: (float(positions[i, 0]), float(positions[i, 1])) for i, node_id in enumerate(ids)}
    return result, f"{count} nodes · force-directed layout"


def _visual_lengths(graph: AssemblyGraph) -> Dict[str, float]:
    lengths = [max(1, node.length) for node in graph.nodes.values()]
    maximum = max(lengths) if lengths else 1
    result = {}
    for node_id, node in graph.nodes.items():
        fraction = max(1, node.length) / maximum
        result[node_id] = 0.035 + 0.56 * fraction
    return result


def edge_endpoint_sides(graph: AssemblyGraph, edge: GraphEdge) -> Tuple[int, int]:
    """Return (source_side, target_side); side 0 = 5' start, 1 = 3' end."""
    if graph.format == "GFA":
        return (1 if not edge.source_reverse else 0, 1 if edge.target_reverse else 0)
    # FASTG lists links from the source 3' end; a prime target is the
    # reverse-complement record, whose 3' end is the original target's end.
    return (1, 1 if edge.target_reverse else 0)


def _circular_length_layout(
    graph: AssemblyGraph, visual: Dict[str, float]
) -> Tuple[
    Dict[str, Tuple[float, float]],
    Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]],
]:
    """Fallback for very large graphs and environments without numpy."""
    ids = list(graph.nodes)
    centers = _circular_layout(graph)
    neighbors: Dict[str, List[str]] = {node_id: [] for node_id in ids}
    for edge in graph.edges:
        if edge.source in neighbors and edge.target in neighbors:
            neighbors[edge.source].append(edge.target)
            neighbors[edge.target].append(edge.source)
    ends = {}
    for index, node_id in enumerate(ids):
        cx, cy = centers[node_id]
        if neighbors[node_id]:
            mx = sum(centers[item][0] for item in neighbors[node_id]) / len(neighbors[node_id])
            my = sum(centers[item][1] for item in neighbors[node_id]) / len(neighbors[node_id])
            dx, dy = mx - cx, my - cy
            length = math.hypot(dx, dy)
            if length < 1e-6:
                angle = 2 * math.pi * index / len(ids)
                dx, dy = math.cos(angle), math.sin(angle)
            else:
                dx, dy = dx / length, dy / length
        else:
            angle = 2 * math.pi * index / len(ids)
            dx, dy = math.cos(angle), math.sin(angle)
        half = visual[node_id] / 2.0
        ends[node_id] = (
            (cx - dx * half, cy - dy * half),
            (cx + dx * half, cy + dy * half),
        )
    return centers, ends


def _component_endpoint_layout(
    ids: List[str],
    edges: List[Tuple[str, str, int, int]],
    visual: Dict[str, float],
    seed: int,
) -> Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Force layout for one connected component, keeping node length visible."""
    count = len(ids)
    if count == 1:
        half = visual[ids[0]] / 2.0
        return {ids[0]: ((-half, 0.0), (half, 0.0))}
    import numpy as np

    index = {node_id: i for i, node_id in enumerate(ids)}
    rng = np.random.default_rng(seed)
    angles = np.linspace(0, 2.0 * math.pi, count, endpoint=False)
    centers = np.column_stack(
        [0.5 + 0.40 * np.cos(angles), 0.5 + 0.40 * np.sin(angles)]
    )
    directions = angles + rng.normal(scale=0.15, size=count)
    half_lengths = np.asarray([visual[node_id] / 2.0 for node_id in ids])
    positions = np.zeros((count * 2, 2), dtype=float)
    positions[0::2, 0] = centers[:, 0] - np.cos(directions) * half_lengths
    positions[0::2, 1] = centers[:, 1] - np.sin(directions) * half_lengths
    positions[1::2, 0] = centers[:, 0] + np.cos(directions) * half_lengths
    positions[1::2, 1] = centers[:, 1] + np.sin(directions) * half_lengths

    internal = np.asarray(
        [(i * 2, i * 2 + 1, visual[node_id]) for i, node_id in enumerate(ids)],
        dtype=float,
    )
    external_list = []
    for source, target, source_side, target_side in edges:
        if source not in index or target not in index:
            continue
        external_list.append(
            (
                index[source] * 2 + source_side,
                index[target] * 2 + target_side,
            )
        )
    external = (
        np.asarray(external_list, dtype=np.int32)
        if external_list
        else np.zeros((0, 2), dtype=np.int32)
    )

    iterations = 320 if count <= 80 else 220 if count <= 200 else 140
    k = 0.055
    temperature = 0.035
    for _ in range(iterations):
        delta = positions[:, None, :] - positions[None, :, :]
        distance = np.sqrt(np.sum(delta * delta, axis=2)) + 1e-5
        magnitude = (k * k) / (distance * distance)
        np.fill_diagonal(magnitude, 0.0)
        # Endpoints of the same segment are held by their internal spring.
        for i in range(count):
            magnitude[i * 2, i * 2 + 1] = 0.0
            magnitude[i * 2 + 1, i * 2] = 0.0
        displacement = np.einsum("ij,ijk->ik", magnitude, delta)

        # Strong internal springs keep the visual length proportional to bp.
        for start, end, rest in internal:
            i, j = int(start), int(end)
            vector = positions[j] - positions[i]
            dist = float(np.hypot(vector[0], vector[1])) + 1e-6
            force = (dist - rest) * 0.55
            unit = vector / dist
            displacement[i] += unit * force
            displacement[j] -= unit * force

        if len(external):
            source = positions[external[:, 0]]
            target = positions[external[:, 1]]
            vector = target - source
            dist = np.sqrt(np.sum(vector * vector, axis=1)) + 1e-6
            force = (dist - 0.008) * 0.55
            step = (force / dist)[:, None] * vector
            np.add.at(displacement, external[:, 0], step)
            np.add.at(displacement, external[:, 1], -step)

        length = np.sqrt(np.sum(displacement * displacement, axis=1)) + 1e-9
        positions += np.minimum(length, temperature)[:, None] * displacement / length[:, None]
        temperature *= 0.995

    # The force layout can shrink some segments against their springs; rescale
    # the component uniformly so typical node spans match the target lengths.
    ratios = []
    for i, node_id in enumerate(ids):
        actual = float(np.linalg.norm(positions[i * 2 + 1] - positions[i * 2]))
        if actual > 1e-9:
            ratios.append(visual[node_id] / actual)
    if ratios:
        factor = float(np.median(ratios))
        if math.isfinite(factor) and 1e-4 < factor < 50.0:
            positions *= factor

    minimum = positions.min(axis=0)
    maximum = positions.max(axis=0)
    centre = (minimum + maximum) / 2.0
    positions -= centre
    result = {}
    for i, node_id in enumerate(ids):
        result[node_id] = (
            (float(positions[i * 2, 0]), float(positions[i * 2, 1])),
            (float(positions[i * 2 + 1, 0]), float(positions[i * 2 + 1, 1])),
        )
    return result


def _pack_endpoint_layouts(
    layouts: List[
        Tuple[
            Tuple[float, float, float, float],
            Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]],
        ]
    ],
    gap: float = 0.10,
    target_aspect: float = 1.45,
) -> Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Pack component layouts into a grid without scaling them down.

    The column count is chosen to make the packed drawing roughly as wide as
    the viewer (``target_aspect``) instead of one very wide row of contigs.
    """
    if not layouts:
        return {}
    if len(layouts) == 1:
        return layouts[0][1]
    layouts = sorted(
        layouts,
        key=lambda item: (item[0][1] - item[0][0]) * (item[0][3] - item[0][2]),
        reverse=True,
    )
    count = len(layouts)
    sizes = []
    for bounds, _ in layouts:
        width = bounds[1] - bounds[0]
        height = bounds[3] - bounds[2]
        sizes.append((max(width, 0.04), max(height, 0.12)))

    best = None
    for columns in range(1, count + 1):
        rows = max(1, int(math.ceil(count / columns)))
        column_widths = [0.0] * columns
        row_heights = [0.0] * rows
        for index, (width, height) in enumerate(sizes):
            column = index % columns
            row = index // columns
            column_widths[column] = max(column_widths[column], width)
            row_heights[row] = max(row_heights[row], height)
        total_width = sum(column_widths) + gap * (columns - 1)
        total_height = sum(row_heights) + gap * (rows - 1)
        ratio = total_width / total_height if total_height > 0 else 1e6
        score = abs(math.log(max(ratio, 1e-6) / target_aspect))
        if best is None or score < best[0]:
            best = (score, columns, rows, column_widths, row_heights)
    _, columns, rows, column_widths, row_heights = best

    column_offsets = []
    cursor = 0.0
    for width in column_widths:
        column_offsets.append(cursor)
        cursor += width + gap
    row_offsets = []
    cursor = 0.0
    for height in row_heights:
        row_offsets.append(cursor)
        cursor += height + gap
    result = {}
    for index, (bounds, ends) in enumerate(layouts):
        column = index % columns
        row = index // columns
        cell_center_x = column_offsets[column] + column_widths[column] / 2.0
        cell_center_y = row_offsets[row] + row_heights[row] / 2.0
        for node_id, (start, end) in ends.items():
            result[node_id] = (
                (start[0] + cell_center_x, start[1] + cell_center_y),
                (end[0] + cell_center_x, end[1] + cell_center_y),
            )
    return result


def layout_graph_with_ends(
    graph: AssemblyGraph,
    *,
    seed: int = 7,
    max_force_nodes: int = 400,
) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]], str]:
    """Layout endpoint pairs so nodes have length and a direction.

    Each segment gets a 5' and a 3' endpoint connected by an internal spring
    whose rest length is proportional to the sequence length.  Links between
    segments are short springs.  Connected components are laid out separately
    and packed into a grid so isolated contigs retain their true length.
    This is the geometry Bandage uses to draw long, curved node tubes.
    """
    ids = list(graph.nodes)
    count = len(ids)
    if count == 0:
        return {}, {}, "empty graph"
    visual = _visual_lengths(graph)
    if count == 1:
        node_id = ids[0]
        half = visual[node_id] / 2.0
        ends = {node_id: ((0.5 - half, 0.5), (0.5 + half, 0.5))}
        return {node_id: (0.5, 0.5)}, ends, "single node"

    if count > max_force_nodes:
        centers, ends = _circular_length_layout(graph, visual)
        return centers, ends, (
            f"{count} nodes: circular layout with length-scaled nodes "
            f"(force layout is limited to {max_force_nodes})"
        )

    try:
        import numpy as np  # noqa: F401
    except ImportError:
        centers, ends = _circular_length_layout(graph, visual)
        return centers, ends, "numpy not found: circular layout with length-scaled nodes"

    components = _node_components(graph)
    layouts = []
    for component_index, members in enumerate(components):
        member_set = set(members)
        edges = []
        for edge in graph.edges:
            if edge.source not in member_set or edge.target not in member_set:
                continue
            source_side, target_side = edge_endpoint_sides(graph, edge)
            edges.append((edge.source, edge.target, source_side, target_side))
        ends = _component_endpoint_layout(
            members, edges, visual, seed + component_index
        )
        points = [point for pair in ends.values() for point in pair]
        layouts.append(
            (
                (
                    min(point[0] for point in points),
                    max(point[0] for point in points),
                    min(point[1] for point in points),
                    max(point[1] for point in points),
                ),
                ends,
            )
        )
    ends_result = _pack_endpoint_layouts(layouts)

    # Uniform scaling preserves the length ratios between nodes.
    points = [point for pair in ends_result.values() for point in pair]
    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)
    span = max(maximum_x - minimum_x, maximum_y - minimum_y, 1e-6)
    scale = 0.94 / span
    centre_x = (minimum_x + maximum_x) / 2.0
    centre_y = (minimum_y + maximum_y) / 2.0

    centers_result = {}
    normalized_ends = {}
    for node_id, (start, end) in ends_result.items():
        new_start = (
            0.5 + (start[0] - centre_x) * scale,
            0.5 + (start[1] - centre_y) * scale,
        )
        new_end = (
            0.5 + (end[0] - centre_x) * scale,
            0.5 + (end[1] - centre_y) * scale,
        )
        normalized_ends[node_id] = (new_start, new_end)
        centers_result[node_id] = (
            (new_start[0] + new_end[0]) / 2.0,
            (new_start[1] + new_end[1]) / 2.0,
        )
    note = f"{count} nodes · length-aware endpoint layout"
    if len(components) > 1:
        note = (
            f"{count} nodes · {len(components)} components · "
            "length-aware endpoint layout"
        )
    return centers_result, normalized_ends, note
