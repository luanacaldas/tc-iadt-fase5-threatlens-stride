"""Gerador de dataset sintético para detecção de componentes arquiteturais.

Gera imagens de diagramas de arquitetura de software com:
- Ícones reconhecíveis por tipo de componente
- Setas de fluxo entre componentes
- Labels de texto
- Anotações YOLO automáticas (classe, cx, cy, w, h normalizados)
- Divisão automática em train/val/test

Uso:
    python scripts/generate_synthetic_dataset.py --count 200 --output dataset

O dataset sintético deve ser combinado com imagens reais para melhores resultados.
"""

from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Classes e mapeamento
# ---------------------------------------------------------------------------

CLASSES = [
    "api_gateway", "backup", "cdn", "compute", "database",
    "identity_provider", "internet", "load_balancer", "monitoring",
    "queue", "secrets_kms", "storage", "user", "waf",
]
CLASS_IDX = {name: i for i, name in enumerate(CLASSES)}

# Cor de fundo por tipo (R, G, B)
COMPONENT_COLORS: dict[str, tuple] = {
    "user":              (70,  130, 180),   # steel blue
    "internet":          (135, 206, 235),   # sky blue
    "waf":               (220,  80,  80),   # vermelho
    "cdn":               (255, 165,   0),   # laranja
    "api_gateway":       (50,  205,  50),   # verde
    "load_balancer":     (144, 238, 144),   # verde claro
    "compute":           (100, 149, 237),   # cornflower blue
    "database":          (147, 112, 219),   # roxo médio
    "storage":           (186,  85, 211),   # roxo
    "queue":             (255, 215,   0),   # dourado
    "monitoring":        (64,  224, 208),   # turquesa
    "backup":            (210, 180, 140),   # tan
    "secrets_kms":       (255, 105, 180),   # rosa
    "identity_provider": (255, 140,   0),   # laranja escuro
}

COMPONENT_ABBR: dict[str, str] = {
    "user":              "USR",
    "internet":          "NET",
    "waf":               "WAF",
    "cdn":               "CDN",
    "api_gateway":       "API",
    "load_balancer":     "LB",
    "compute":           "SVC",
    "database":          "DB",
    "storage":           "S3",
    "queue":             "MQ",
    "monitoring":        "LOG",
    "backup":            "BKP",
    "secrets_kms":       "KMS",
    "identity_provider": "IdP",
}

IMG_W = 800
IMG_H = 600
COMP_W = 90
COMP_H = 60
PADDING = 20


# ---------------------------------------------------------------------------
# Ícones por tipo
# ---------------------------------------------------------------------------

def draw_component(draw: ImageDraw.ImageDraw, comp_type: str, x: int, y: int, w: int, h: int) -> None:
    """Desenha o ícone do componente na posição (x, y) com dimensões (w, h)."""
    color = COMPONENT_COLORS.get(comp_type, (128, 128, 128))
    border = tuple(max(0, c - 50) for c in color)
    abbr = COMPONENT_ABBR.get(comp_type, comp_type[:3].upper())

    if comp_type == "database":
        _draw_cylinder(draw, x, y, w, h, color, border)
    elif comp_type == "user":
        _draw_person(draw, x, y, w, h, color, border)
    elif comp_type == "internet":
        _draw_cloud(draw, x, y, w, h, color, border)
    elif comp_type in ("storage", "backup"):
        _draw_bucket(draw, x, y, w, h, color, border)
    elif comp_type == "queue":
        _draw_queue_shape(draw, x, y, w, h, color, border)
    else:
        _draw_box(draw, x, y, w, h, color, border)

    # Label abreviada
    try:
        font = ImageFont.load_default(size=11)
    except Exception:
        font = ImageFont.load_default()
    draw.text(
        (x + w // 2, y + h // 2),
        abbr,
        fill="white",
        font=font,
        anchor="mm",
    )


def _draw_box(draw, x, y, w, h, fill, border):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=fill, outline=border, width=2)


def _draw_cylinder(draw, x, y, w, h, fill, border):
    top_h = h // 5
    draw.rectangle([x, y + top_h, x + w, y + h], fill=fill, outline=border, width=2)
    draw.ellipse([x, y, x + w, y + top_h * 2], fill=fill, outline=border, width=2)
    draw.line([x, y + top_h, x, y + h], fill=border, width=2)
    draw.line([x + w, y + top_h, x + w, y + h], fill=border, width=2)
    draw.arc([x, y + h - top_h, x + w, y + h + top_h], start=0, end=180, fill=border, width=2)


def _draw_person(draw, x, y, w, h, fill, border):
    head_r = h // 5
    cx = x + w // 2
    cy_head = y + head_r + 4
    draw.ellipse([cx - head_r, cy_head - head_r, cx + head_r, cy_head + head_r], fill=fill, outline=border, width=2)
    body_top = cy_head + head_r + 2
    body_bot = y + h - 4
    draw.rounded_rectangle([cx - w // 4, body_top, cx + w // 4, body_bot], radius=4, fill=fill, outline=border, width=2)


def _draw_cloud(draw, x, y, w, h, fill, border):
    bumps = [(0.15, 0.6, 0.22), (0.35, 0.5, 0.20), (0.55, 0.45, 0.22), (0.75, 0.55, 0.18), (0.88, 0.65, 0.15)]
    for bx, by, br in bumps:
        cx = int(x + bx * w)
        cy = int(y + by * h)
        r = int(br * min(w, h))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=border, width=1)
    draw.rectangle([x + int(0.1 * w), y + int(0.6 * h), x + int(0.9 * w), y + h], fill=fill)
    draw.line([x + int(0.1 * w), y + int(0.6 * h), x + int(0.1 * w), y + h], fill=border, width=2)
    draw.line([x + int(0.9 * w), y + int(0.6 * h), x + int(0.9 * w), y + h], fill=border, width=2)
    draw.line([x + int(0.1 * w), y + h, x + int(0.9 * w), y + h], fill=border, width=2)


def _draw_bucket(draw, x, y, w, h, fill, border):
    pts = [x, y, x + w, y, x + int(0.85 * w), y + h, x + int(0.15 * w), y + h]
    draw.polygon(pts, fill=fill, outline=border)


def _draw_queue_shape(draw, x, y, w, h, fill, border):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill, outline=border, width=2)
    slot_w = w // 5
    for i in range(1, 4):
        sx = x + i * slot_w
        draw.line([sx, y + 6, sx, y + h - 6], fill=border, width=1)


# ---------------------------------------------------------------------------
# Setas
# ---------------------------------------------------------------------------

def draw_arrow(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    draw.line([x1, y1, x2, y2], fill=(80, 80, 80), width=2)
    # Cabeça da seta
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 10
    for delta in (+0.4, -0.4):
        ax = x2 - int(arrow_len * math.cos(angle + delta))
        ay = y2 - int(arrow_len * math.sin(angle + delta))
        draw.line([x2, y2, ax, ay], fill=(80, 80, 80), width=2)


# ---------------------------------------------------------------------------
# Layouts de arquitetura
# ---------------------------------------------------------------------------

def _layout_linear(components: list[str]) -> list[tuple[str, int, int]]:
    """Componentes em linha horizontal."""
    n = len(components)
    step = (IMG_W - 2 * PADDING - COMP_W) // max(n - 1, 1)
    return [
        (comp, PADDING + i * step, (IMG_H - COMP_H) // 2)
        for i, comp in enumerate(components)
    ]


def _layout_layered(components: list[str]) -> list[tuple[str, int, int]]:
    """Componentes em camadas (estilo enterprise)."""
    rows: list[list[str]] = []
    remaining = list(components)
    while remaining:
        row_size = random.randint(1, min(4, len(remaining)))
        rows.append(remaining[:row_size])
        remaining = remaining[row_size:]

    positions = []
    row_h = (IMG_H - 2 * PADDING - COMP_H) // max(len(rows), 1)
    for ri, row in enumerate(rows):
        col_w = (IMG_W - 2 * PADDING - COMP_W) // max(len(row) - 1, 1)
        for ci, comp in enumerate(row):
            x = PADDING + ci * col_w if len(row) > 1 else (IMG_W - COMP_W) // 2
            y = PADDING + ri * row_h
            positions.append((comp, x, y))
    return positions


def _layout_hub(components: list[str]) -> list[tuple[str, int, int]]:
    """Um componente central com os demais ao redor."""
    import math
    center_comp = components[0]
    others = components[1:]
    cx, cy = IMG_W // 2, IMG_H // 2
    positions = [(center_comp, cx - COMP_W // 2, cy - COMP_H // 2)]
    radius = min(IMG_W, IMG_H) // 2 - COMP_W
    for i, comp in enumerate(others):
        angle = 2 * math.pi * i / len(others)
        x = int(cx + radius * math.cos(angle)) - COMP_W // 2
        y = int(cy + radius * math.sin(angle)) - COMP_H // 2
        x = max(PADDING, min(IMG_W - COMP_W - PADDING, x))
        y = max(PADDING, min(IMG_H - COMP_H - PADDING, y))
        positions.append((comp, x, y))
    return positions


def _pick_layout(components: list[str]) -> list[tuple[str, int, int]]:
    choice = random.choice(["linear", "layered", "hub"])
    if choice == "linear" and len(components) <= 5:
        return _layout_linear(components)
    elif choice == "hub":
        return _layout_hub(components)
    return _layout_layered(components)


def generate_layout(seed: int) -> list[tuple[str, int, int]]:
    """Reproduce component order and positions without rendering the image."""
    random.seed(seed)
    base_sequence = random.choice(TYPICAL_SEQUENCES)
    components = list(base_sequence)
    if random.random() < 0.3 and len(components) > 3:
        remove_idx = random.randint(1, len(components) - 2)
        components.pop(remove_idx)
    if random.random() < 0.3:
        extras = [component for component in CLASSES if component not in components]
        if extras:
            components.insert(random.randint(1, len(components)), random.choice(extras))

    seen: set[str] = set()
    components = [component for component in components if not (component in seen or seen.add(component))]  # type: ignore[func-returns-value]
    return _pick_layout(components)


def structure_from_layout(positions: list[tuple[str, int, int]]) -> dict:
    components = []
    component_ids = []
    type_counts: dict[str, int] = {}
    for component_type, x, y in positions:
        type_counts[component_type] = type_counts.get(component_type, 0) + 1
        component_id = f"{component_type}_{type_counts[component_type]}"
        component_ids.append(component_id)
        components.append(
            {
                "id": component_id,
                "type": component_type,
                "bbox": [x, y, x + COMP_W, y + COMP_H],
            }
        )
    flows = [
        {
            "id": f"f{index + 1}",
            "from": component_ids[index],
            "to": component_ids[index + 1],
            "protocol": "unknown",
        }
        for index in range(len(component_ids) - 1)
    ]
    return {"components": components, "flows": flows, "trustBoundaries": []}


# ---------------------------------------------------------------------------
# Geração de uma imagem
# ---------------------------------------------------------------------------

TYPICAL_SEQUENCES = [
    ["user", "internet", "waf", "api_gateway", "compute", "database"],
    ["user", "internet", "cdn", "waf", "api_gateway", "load_balancer", "compute", "database", "monitoring"],
    ["user", "internet", "api_gateway", "compute", "database", "secrets_kms"],
    ["user", "identity_provider", "api_gateway", "compute", "database", "monitoring", "backup"],
    ["user", "internet", "waf", "load_balancer", "compute", "queue", "compute", "database", "storage"],
    ["user", "internet", "cdn", "api_gateway", "compute", "database", "storage", "monitoring"],
    ["user", "internet", "waf", "api_gateway", "identity_provider", "compute", "database", "secrets_kms", "backup"],
]

BG_COLORS = [
    (248, 249, 250),  # branco acinzentado
    (240, 244, 248),  # azul muito claro
    (245, 245, 245),  # cinza claro
    (255, 255, 255),  # branco
]


def generate_image(seed: int) -> tuple[Image.Image, list[tuple[int, int, int, int, int]]]:
    """Gera uma imagem sintética e retorna (imagem, anotações YOLO).

    Anotações: lista de (class_idx, cx_norm, cy_norm, w_norm, h_norm).
    """
    positions = generate_layout(seed)

    # Fundo
    bg_color = random.choice(BG_COLORS)
    img = Image.new("RGB", (IMG_W, IMG_H), bg_color)
    draw = ImageDraw.Draw(img)

    # Grade de fundo (opcional)
    if random.random() < 0.4:
        grid_color = tuple(max(0, c - 15) for c in bg_color)
        for gx in range(0, IMG_W, 40):
            draw.line([(gx, 0), (gx, IMG_H)], fill=grid_color, width=1)
        for gy in range(0, IMG_H, 40):
            draw.line([(0, gy), (IMG_W, gy)], fill=grid_color, width=1)

    # Setas entre componentes consecutivos
    for i in range(len(positions) - 1):
        _, x1, y1 = positions[i]
        _, x2, y2 = positions[i + 1]
        cx1 = x1 + COMP_W
        cy1 = y1 + COMP_H // 2
        cx2 = x2
        cy2 = y2 + COMP_H // 2
        draw_arrow(draw, cx1, cy1, cx2, cy2)

    # Componentes + labels
    try:
        label_font = ImageFont.load_default(size=9)
    except Exception:
        label_font = ImageFont.load_default()

    annotations: list[tuple[int, int, int, int, int]] = []
    for comp_type, x, y in positions:
        draw_component(draw, comp_type, x, y, COMP_W, COMP_H)

        # Rótulo abaixo do componente
        label = comp_type.replace("_", " ").title()
        draw.text((x + COMP_W // 2, y + COMP_H + 8), label, fill=(80, 80, 80), font=label_font, anchor="mt")

        # Anotação YOLO (normalizada)
        cx_norm = (x + COMP_W / 2) / IMG_W
        cy_norm = (y + COMP_H / 2) / IMG_H
        w_norm = COMP_W / IMG_W
        h_norm = COMP_H / IMG_H
        annotations.append((CLASS_IDX[comp_type], cx_norm, cy_norm, w_norm, h_norm))

    # Título opcional
    if random.random() < 0.5:
        titles = [
            "Cloud Architecture", "System Overview", "Microservices Architecture",
            "API Architecture", "AWS Architecture", "Azure Architecture",
            "Backend Services", "Data Flow Diagram",
        ]
        try:
            title_font = ImageFont.load_default(size=14)
        except Exception:
            title_font = ImageFont.load_default()
        draw.text((IMG_W // 2, 16), random.choice(titles), fill=(40, 40, 40), font=title_font, anchor="mt")

    return img, annotations


# ---------------------------------------------------------------------------
# Gravação de anotações
# ---------------------------------------------------------------------------

def write_annotation(label_path: Path, annotations: list[tuple]) -> None:
    lines = [f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cls, cx, cy, w, h in annotations]
    label_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Gera dataset sintético para YOLOv8")
    parser.add_argument("--count", type=int, default=200, help="Total de imagens a gerar (default: 200)")
    parser.add_argument("--output", type=str, default="dataset", help="Pasta de saída (default: dataset)")
    parser.add_argument("--seed", type=int, default=42, help="Seed base para reprodutibilidade")
    args = parser.parse_args()

    output = Path(args.output)

    # Splits: 70% train, 20% val, 10% test
    n_train = int(args.count * 0.70)
    n_val = int(args.count * 0.20)
    n_test = args.count - n_train - n_val
    splits = [("train", n_train), ("val", n_val), ("test", n_test)]

    for split, n in splits:
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)

    total = 0
    for split, n in splits:
        print(f"  Gerando {n} imagens para {split} ...")
        for i in range(n):
            seed = args.seed * 1000 + total
            img, annotations = generate_image(seed)
            fname = f"arch_{split}_{i:04d}"
            img.save(output / "images" / split / f"{fname}.jpg", quality=92)
            write_annotation(output / "labels" / split / f"{fname}.txt", annotations)
            total += 1

    print(f"\nDataset sintético gerado: {total} imagens em '{output}/'")
    print(f"  train: {n_train} | val: {n_val} | test: {n_test}")
    print(f"\nClasses ({len(CLASSES)}):")
    for i, cls in enumerate(CLASSES):
        print(f"  {i}: {cls}")
    print(f"\nPróximo passo: python scripts/train_yolo.py")


if __name__ == "__main__":
    main()
