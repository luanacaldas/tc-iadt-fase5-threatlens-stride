from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.cloud_class_mapping import CANONICAL_CLASSES, normalize_class_name
from scripts.create_training_bundle import create_bundle
from scripts.kaggle_dataset_utils import (
    annotation_to_yolo_lines,
    deterministic_split,
    parse_augmented_filename,
    parse_voc_annotation,
)
from scripts.prepare_kaggle_dataset import prepare_dataset
from scripts.download_kaggle_subset import build_selection_plan
from scripts.merge_yolo_datasets import merge_datasets


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_XML = ROOT / "dataset" / "fixtures" / "kaggle" / "aws_amazon_api_gateway_0000_aug_0.xml"


class KaggleFilenameTests(unittest.TestCase):
    def test_augmented_filename_is_grouped_by_original_architecture(self) -> None:
        parsed = parse_augmented_filename(
            "src/dataset/dataset_augmented/aws_amazon_api_gateway_0000_aug_9.png"
        )
        self.assertEqual(parsed.group_id, "aws_amazon_api_gateway_0000")
        self.assertEqual(parsed.primary_class, "aws_amazon_api_gateway")
        self.assertEqual(parsed.source_index, "0000")
        self.assertEqual(parsed.augmentation_index, 9)
        self.assertEqual(parsed.provider_hint, "aws")

    def test_split_is_stable_for_all_variants_in_a_group(self) -> None:
        values = {
            deterministic_split(
                "aws_amazon_api_gateway_0000",
                "aws_amazon_api_gateway",
                0.70,
                0.15,
                "test-seed",
            )
            for _ in range(10)
        }
        self.assertEqual(len(values), 1)


class CloudMappingTests(unittest.TestCase):
    def test_provider_specific_labels_map_to_canonical_roles(self) -> None:
        expected = {
            "aws_amazon_api_gateway": "api_gateway",
            "azure_sql_server": "database",
            "azure_monitor": "monitoring",
            "aws_amazon_simple_queue_service": "queue",
            "aws_amazon_elastic_kubernetes_service": "compute",
            "gcp_cloud_storage": "storage",
            "aws_lambda_lambda_function": "compute",
        }
        for raw_class, canonical in expected.items():
            with self.subTest(raw_class=raw_class):
                self.assertEqual(normalize_class_name(raw_class), canonical)


class PascalVocTests(unittest.TestCase):
    def test_real_kaggle_xml_is_parsed_and_converted(self) -> None:
        annotation = parse_voc_annotation(FIXTURE_XML, normalize_class_name)
        self.assertEqual(annotation.width, 2916)
        self.assertEqual(annotation.height, 2316)
        self.assertEqual(len(annotation.objects), 11)

        lines, rejected = annotation_to_yolo_lines(annotation, CANONICAL_CLASSES)
        self.assertEqual(len(lines), 10)
        self.assertEqual(rejected["unmapped"], 1)
        self.assertTrue(all(len(line.split()) == 5 for line in lines))

    def test_dry_run_reports_no_group_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            output = Path(temp_dir) / "output"
            source.mkdir()
            xml_path = source / FIXTURE_XML.name
            shutil.copy2(FIXTURE_XML, xml_path)
            xml_path.with_suffix(".png").write_bytes(b"fixture")

            summary = prepare_dataset(
                source_root=source,
                output_root=output,
                train_ratio=0.70,
                val_ratio=0.15,
                seed="test-seed",
                max_augmentations=4,
                link_mode="copy",
                dry_run=True,
            )

            self.assertEqual(summary["discovered_pairs"], 1)
            self.assertEqual(summary["augmentation_groups"], 1)
            self.assertEqual(summary["selected_pairs"], 1)
            self.assertEqual(summary["split_leakage_groups"], [])


class KaggleSubsetPlanTests(unittest.TestCase):
    def test_plan_pairs_files_and_respects_size_limit(self) -> None:
        base = "src/dataset/dataset_augmented/aws_amazon_api_gateway_0000_aug_0"
        large = "src/dataset/dataset_augmented/aws_amazon_api_gateway_0000_aug_1"
        manifest = {
            "dataset": "carlosrian/software-architecture-dataset",
            "files": [
                {
                    "name": f"{base}.png",
                    "size_bytes": 500_000,
                    "role": "image",
                    "pair_key": base,
                    "group_id": "aws_amazon_api_gateway_0000",
                    "primary_class": "aws_amazon_api_gateway",
                    "provider_hint": "aws",
                },
                {
                    "name": f"{base}.xml",
                    "size_bytes": 2_500,
                    "role": "annotation",
                    "pair_key": base,
                    "group_id": "aws_amazon_api_gateway_0000",
                    "primary_class": "aws_amazon_api_gateway",
                    "provider_hint": "aws",
                },
                {
                    "name": f"{large}.png",
                    "size_bytes": 20_000_000,
                    "role": "image",
                    "pair_key": large,
                    "group_id": "aws_amazon_api_gateway_0000",
                    "primary_class": "aws_amazon_api_gateway",
                    "provider_hint": "aws",
                },
                {
                    "name": f"{large}.xml",
                    "size_bytes": 2_500,
                    "role": "annotation",
                    "pair_key": large,
                    "group_id": "aws_amazon_api_gateway_0000",
                    "primary_class": "aws_amazon_api_gateway",
                    "provider_hint": "aws",
                },
            ],
        }

        plan = build_selection_plan(
            manifest=manifest,
            groups_per_primary_class=1,
            augmentations_per_group=3,
            max_image_bytes=8_000_000,
            seed="test-seed",
            include_unmapped=False,
        )

        self.assertEqual(plan["summary"]["selected_groups"], 1)
        self.assertEqual(plan["summary"]["selected_pairs"], 1)
        self.assertEqual(plan["summary"]["estimated_image_bytes"], 500_000)
        self.assertEqual(plan["summary"]["estimated_annotation_bytes"], 2_500)


class HybridMergeTests(unittest.TestCase):
    @staticmethod
    def _create_source(root: Path, images_by_split: dict[str, list[str]]) -> None:
        (root / "architecture.yaml").parent.mkdir(parents=True, exist_ok=True)
        (root / "architecture.yaml").write_text(
            "path: .\ntrain: images/train\nval: images/val\ntest: images/test\n"
            "nc: 1\nnames:\n  0: compute\n",
            encoding="utf-8",
        )
        for split in ("train", "val", "test"):
            image_dir = root / "images" / split
            label_dir = root / "labels" / split
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            for filename in images_by_split.get(split, []):
                (image_dir / filename).write_bytes(b"image")
                (label_dir / f"{Path(filename).stem}.txt").write_text(
                    "0 0.5 0.5 0.2 0.2\n",
                    encoding="utf-8",
                )

    def test_merge_writes_counts_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_a = root / "source_a"
            source_b = root / "source_b"
            output = root / "hybrid"
            self._create_source(source_a, {"train": ["aws_compute_0000_aug_0.png"]})
            self._create_source(source_b, {"val": ["aws_compute_0000_aug_0.png"]})

            summary = merge_datasets(
                [("source_a", source_a), ("source_b", source_b)],
                output,
                "copy",
            )

            self.assertEqual(summary["total_images"], 2)
            self.assertEqual(summary["class_distribution"], {"compute": 2})
            self.assertEqual(summary["provenance_rows"], 2)
            self.assertEqual(summary["leakage_groups"], [])
            provenance = (output / "reports" / "provenance.csv").read_text(encoding="utf-8")
            self.assertIn("source_a", provenance)
            self.assertIn("source_b", provenance)

    def test_merge_rejects_group_leakage_across_splits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            self._create_source(
                source,
                {
                    "train": ["aws_compute_0000_aug_0.png"],
                    "val": ["aws_compute_0000_aug_1.png"],
                },
            )

            with self.assertRaisesRegex(RuntimeError, "Group leakage"):
                merge_datasets([("source", source)], root / "hybrid", "copy")


class TrainingBundleTests(unittest.TestCase):
    def test_bundle_contains_portable_training_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = root / "dataset"
            HybridMergeTests._create_source(
                dataset,
                {"train": ["aws_compute_0000_aug_0.png"]},
            )
            output = root / "training-bundle.zip"

            summary = create_bundle(dataset, output)

            self.assertEqual(summary["images"], 1)
            self.assertEqual(summary["labels"], 1)
            self.assertEqual(len(summary["sha256"]), 64)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = set(archive.namelist())
            self.assertIn(
                "threatlens_training/dataset/hybrid_v2/architecture.yaml",
                names,
            )
            self.assertIn("threatlens_training/scripts/train_yolo.py", names)


if __name__ == "__main__":
    unittest.main()
