"""Download de datasets públicos de diagramas de arquitetura do Roboflow Universe.

Uso:
    # Instale primeiro: pip install roboflow
    python scripts/download_roboflow_dataset.py --api-key SUA_API_KEY

A API key do Roboflow é GRATUITA em: https://app.roboflow.com
Crie uma conta, vá em Settings > API Keys e copie a chave.

Datasets públicos sugeridos no Roboflow Universe:
  - "cloud-architecture-diagrams"
  - "aws-architecture-icons"
  - "network-diagram-detection"

O script tenta os datasets em ordem e combina os que encontrar.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

# Datasets públicos conhecidos no Roboflow Universe com componentes de arquitetura
# Formato: (workspace, project, version)
CANDIDATE_DATASETS = [
    ("roboflow-100", "cloud-architecture-diagrams", 1),
    ("architecture-detection", "software-architecture", 1),
    ("network-diagrams", "network-topology-detection", 1),
]


def download_dataset(api_key: str, workspace: str, project: str, version: int, output_dir: Path) -> bool:
    """Tenta baixar um dataset do Roboflow. Retorna True se bem-sucedido."""
    try:
        from roboflow import Roboflow

        rf = Roboflow(api_key=api_key)
        proj = rf.workspace(workspace).project(project)
        dataset = proj.version(version).download("yolov8", location=str(output_dir / "roboflow_raw"))
        print(f"  Download concluído: {dataset.location}")
        return True
    except ImportError:
        print("  [erro] Pacote 'roboflow' não instalado. Execute: pip install roboflow")
        return False
    except Exception as exc:
        print(f"  [aviso] Dataset {workspace}/{project} indisponível: {exc}")
        return False


def merge_into_dataset(source_dir: Path, target_dir: Path) -> int:
    """Copia imagens e labels de source_dir para target_dir preservando a estrutura."""
    copied = 0
    for split in ("train", "valid", "val", "test"):
        src_images = source_dir / split / "images" if (source_dir / split / "images").exists() else source_dir / "images" / split
        src_labels = source_dir / split / "labels" if (source_dir / split / "labels").exists() else source_dir / "labels" / split

        dest_split = "val" if split == "valid" else split
        dst_images = target_dir / "images" / dest_split
        dst_labels = target_dir / "labels" / dest_split
        dst_images.mkdir(parents=True, exist_ok=True)
        dst_labels.mkdir(parents=True, exist_ok=True)

        if src_images.exists():
            for img_file in src_images.glob("*"):
                shutil.copy2(img_file, dst_images / img_file.name)
                copied += 1
        if src_labels.exists():
            for lbl_file in src_labels.glob("*.txt"):
                shutil.copy2(lbl_file, dst_labels / lbl_file.name)

    return copied


def main():
    parser = argparse.ArgumentParser(description="Download datasets do Roboflow para treino YOLOv8")
    parser.add_argument("--api-key", required=True, help="API key do Roboflow (grátis em app.roboflow.com)")
    parser.add_argument("--output", default="dataset", help="Pasta de saída (default: dataset)")
    parser.add_argument("--workspace", default="", help="Workspace específico (opcional)")
    parser.add_argument("--project", default="", help="Projeto específico (opcional)")
    parser.add_argument("--version", type=int, default=1, help="Versão do projeto (default: 1)")
    args = parser.parse_args()

    output = Path(args.output)
    temp_dir = output / "_roboflow_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0

    if args.workspace and args.project:
        # Download de projeto específico
        datasets_to_try = [(args.workspace, args.project, args.version)]
    else:
        datasets_to_try = CANDIDATE_DATASETS

    for workspace, project, version in datasets_to_try:
        print(f"\nTentando: {workspace}/{project} v{version} ...")
        if download_dataset(args.api_key, workspace, project, version, temp_dir):
            raw_dir = temp_dir / "roboflow_raw"
            count = merge_into_dataset(raw_dir, output)
            downloaded += count
            print(f"  Adicionadas {count} imagens ao dataset.")
            shutil.rmtree(raw_dir, ignore_errors=True)

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    if downloaded == 0:
        print("\n[aviso] Nenhum dataset foi baixado automaticamente.")
        print("Opções:")
        print("  1. Acesse https://universe.roboflow.com e busque 'architecture diagram'")
        print("  2. Baixe manualmente em formato YOLOv8 e coloque em dataset/images/ e dataset/labels/")
        print("  3. Use o gerador sintético: python scripts/generate_synthetic_dataset.py --count 300")
    else:
        print(f"\nTotal: {downloaded} imagens baixadas em '{output}/'")
        print("Próximo passo: python scripts/train_yolo.py")


if __name__ == "__main__":
    main()
