from __future__ import annotations

import unittest
import tempfile
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw

from backend.detector import (
    _apply_confidence_calibration,
    _cluster_repeated_ocr_proposals,
    _extract_colored_anchors,
    _infer_flows,
    _infer_diagram_provider,
    _infer_provider,
    _ocr_component_proposals,
    _ocr_label_is_compatible,
    _proposal_bbox_from_label,
    _proposal_bbox_from_visual_anchor,
    _resolve_semantic_conflicts,
    _resolve_semantic_proposal_conflicts,
    _semantic_type_from_label,
    _stacked_ocr_phrases,
)
from backend.diagram_structure import boundary_ids_crossed, detect_flows, detect_trust_boundaries
from backend.main import (
    _build_evidence_catalog,
    _build_response,
    _reconcile_trust_boundary_crossings,
    _read_validated_image,
    _readiness_summary,
    _trace_threat,
    _validate_architecture_payload,
    _validate_report_locally,
)
from backend.pdf_report import _safe
from backend.rag import _doc_id, _query_lexical
from backend.ocr import _normalize_protocol_text, apply_protocol_evidence, match_component_label
from backend.stride_engine import analyze_architecture, normalize_architecture
from scripts.train_yolo import _augmentation_config, _label_for_image, _list_images


class DetectorContractTests(unittest.TestCase):
    def test_confidence_calibration_is_bounded_and_auditable(self) -> None:
        calibrated = _apply_confidence_calibration(
            0.9,
            0.01,
            {"coef": [0.5, 0.1], "intercept": -0.4},
        )

        self.assertGreaterEqual(calibrated, 0.0)
        self.assertLessEqual(calibrated, 1.0)

    def test_explicit_ocr_service_label_creates_review_only_proposal(self) -> None:
        proposals = _ocr_component_proposals(
            [{"text": "Cloud Load Balancer", "confidence": 0.93, "bbox": [100, 80, 230, 100], "engine": "tesseract"}],
            (500, 300),
        )

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["type"], "load_balancer")
        self.assertEqual(proposals[0]["reviewStatus"], "pending")
        self.assertEqual(proposals[0]["metadata"]["detectionSource"], "semantic_ocr_proposal")

    def test_ocr_proposal_localizes_icon_above_label(self) -> None:
        bbox = _proposal_bbox_from_label([180, 160, 320, 180], (500, 300))

        self.assertLess(bbox[1], 160)
        self.assertLessEqual(bbox[3], 167)
        self.assertLessEqual(bbox[2] - bbox[0], 70)

    def test_gcp_ocr_proposal_uses_inline_card_geometry(self) -> None:
        proposals = _ocr_component_proposals(
            [{"text": "Google Cloud Armor", "confidence": 0.94, "bbox": [210, 90, 330, 112]}],
            (600, 400),
        )

        self.assertEqual(proposals[0]["provider"], "gcp")
        self.assertEqual(proposals[0]["metadata"]["localizationMethod"], "inline_card")
        self.assertGreater(proposals[0]["bbox"][3], 101)

    def test_visual_anchor_supports_label_above_icon(self) -> None:
        bbox, method = _proposal_bbox_from_visual_anchor(
            [100, 50, 160, 70],
            [[105, 90, 155, 145]],
            (400, 240),
        )

        self.assertEqual(method, "visual_anchor_below_label")
        self.assertLessEqual(bbox[1], 50)
        self.assertGreaterEqual(bbox[3], 145)

    def test_visual_anchor_policy_is_limited_to_high_resolution_azure_diagrams(self) -> None:
        lines = [{"text": "Azure App Service", "confidence": 0.96, "bbox": [500, 420, 650, 450]}]
        anchors = [[525, 300, 625, 395]]

        large = _ocr_component_proposals(lines, (1200, 900), visual_anchors=anchors)
        small = _ocr_component_proposals(lines, (800, 600), visual_anchors=anchors)

        self.assertTrue(large[0]["metadata"]["localizationMethod"].startswith("visual_anchor_"))
        self.assertEqual(small[0]["metadata"]["localizationMethod"], "label_below_icon")

    def test_small_azure_diagram_accepts_icon_below_label(self) -> None:
        lines = [{"text": "Azure App Service", "confidence": 0.96, "bbox": [300, 180, 440, 205]}]
        anchors = [[320, 235, 420, 330]]

        proposals = _ocr_component_proposals(lines, (800, 600), visual_anchors=anchors)

        self.assertEqual(proposals[0]["metadata"]["localizationMethod"], "visual_anchor_below_label")

    def test_adjacent_replicas_are_grouped_without_losing_provenance(self) -> None:
        proposals = [
            {
                "id": f"compute_ocr_{index}",
                "name": "Virtual Machine",
                "type": "compute",
                "ocrLabel": "Virtual Machine",
                "bbox": [100 + index * 62, 80, 158 + index * 62, 145],
                "confidence": 0.65,
                "metadata": {"detectionSource": "semantic_ocr_proposal"},
            }
            for index in range(3)
        ]

        grouped = _cluster_repeated_ocr_proposals(proposals, (600, 400))

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["metadata"]["instanceCount"], 3)
        self.assertEqual(len(grouped[0]["metadata"]["groupedProposalIds"]), 3)

    def test_colored_visual_anchor_extraction_ignores_white_background(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "anchor.png"
            image = Image.new("RGB", (320, 200), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((120, 55, 185, 125), fill=(0, 130, 220))
            image.save(path)

            anchors = _extract_colored_anchors(str(path))

        self.assertTrue(anchors)
        self.assertTrue(any(anchor[0] <= 120 and anchor[2] >= 185 for anchor in anchors))

    def test_semantic_taxonomy_covers_development_service_roles(self) -> None:
        self.assertEqual(_semantic_type_from_label("OpenSearch Handler"), "compute")
        self.assertEqual(_semantic_type_from_label("Azure AI Search"), "storage")
        self.assertEqual(_semantic_type_from_label("Amazon SES"), "queue")
        self.assertEqual(_semantic_type_from_label("VPN Gateway"), "api_gateway")

    def test_explicit_waf_wins_over_gateway_ambiguity(self) -> None:
        self.assertEqual(_semantic_type_from_label("Application Gateway with WAF"), "waf")

    def test_conflicting_yolo_type_does_not_block_semantic_ocr_proposal(self) -> None:
        existing = [{"id": "compute_1", "type": "compute", "bbox": [180, 80, 280, 180]}]
        proposals = _ocr_component_proposals(
            [{"text": "Azure AI Search", "confidence": 0.96, "bbox": [185, 155, 275, 178]}],
            (500, 300),
            existing=existing,
        )

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["type"], "storage")

    def test_semantic_conflict_preserves_supervised_hypothesis_as_alternative(self) -> None:
        supervised = [{
            "id": "database_1",
            "type": "database",
            "bbox": [100, 80, 180, 160],
            "ocrEvidence": {
                "text": "App Service",
                "bbox": [110, 145, 175, 160],
                "accepted": False,
                "semanticType": "compute",
            },
            "metadata": {"detectionSource": "supervised_yolo"},
        }]
        proposals = [{
            "id": "compute_ocr_1",
            "type": "compute",
            "bbox": [95, 70, 185, 165],
            "ocrEvidence": {"bbox": [110, 145, 175, 160]},
        }]

        active, alternatives = _resolve_semantic_conflicts(supervised, proposals, (500, 300))

        self.assertEqual(active, [])
        self.assertEqual(alternatives[0]["metadata"]["supersededBy"], "compute_ocr_1")

    def test_nearby_semantic_anchor_supersedes_conflicting_yolo_hypothesis(self) -> None:
        supervised = [{
            "id": "database_1",
            "type": "database",
            "bbox": [100, 80, 180, 160],
            "ocrEvidence": None,
            "metadata": {"detectionSource": "supervised_yolo"},
        }]
        proposals = [{
            "id": "storage_ocr_1",
            "type": "storage",
            "bbox": [118, 92, 198, 172],
            "metadata": {"detectionSource": "semantic_ocr_proposal"},
        }]

        active, alternatives = _resolve_semantic_conflicts(supervised, proposals, (500, 300))

        self.assertEqual(active, [])
        self.assertEqual(alternatives[0]["metadata"]["supersededBy"], "storage_ocr_1")
        self.assertEqual(
            alternatives[0]["metadata"]["supersededReason"],
            "semantic_anchor_spatial_conflict",
        )

    def test_same_type_semantic_anchor_protects_yolo_from_ambient_conflict(self) -> None:
        supervised = [{
            "id": "compute_1",
            "type": "compute",
            "bbox": [100, 80, 180, 160],
            "ocrEvidence": None,
            "metadata": {"detectionSource": "supervised_yolo"},
        }]
        proposals = [
            {"id": "compute_ocr_1", "type": "compute", "bbox": [115, 92, 195, 172]},
            {"id": "storage_ocr_1", "type": "storage", "bbox": [135, 100, 215, 180]},
        ]

        active, alternatives = _resolve_semantic_conflicts(supervised, proposals, (500, 300))

        self.assertEqual([item["id"] for item in active], ["compute_1"])
        self.assertEqual(alternatives, [])

    def test_more_specific_semantic_label_wins_shared_visual_anchor(self) -> None:
        proposals = [
            {
                "id": "api_gateway_ocr_1",
                "name": "Application Gateway",
                "type": "api_gateway",
                "bbox": [100, 80, 200, 180],
                "ocrLabel": "Application Gateway",
                "confidence": 0.65,
                "ocrEvidence": {"semanticStackDepth": 1},
                "metadata": {"detectionSource": "semantic_ocr_proposal"},
            },
            {
                "id": "waf_ocr_1",
                "name": "Application Gateway with Azure WAF",
                "type": "waf",
                "bbox": [100, 80, 200, 180],
                "ocrLabel": "Application Gateway with Azure WAF",
                "confidence": 0.66,
                "ocrEvidence": {"semanticStackDepth": 1},
                "metadata": {"detectionSource": "semantic_ocr_proposal"},
            },
        ]

        active, alternatives = _resolve_semantic_proposal_conflicts(proposals)

        self.assertEqual([item["id"] for item in active], ["waf_ocr_1"])
        self.assertEqual(alternatives[0]["metadata"]["supersededBy"], "waf_ocr_1")
        self.assertEqual(
            alternatives[0]["metadata"]["supersededReason"],
            "shared_visual_anchor_semantic_conflict",
        )

    def test_diagram_provider_propagates_to_generic_gcp_labels(self) -> None:
        lines = [
            {"text": "Google Cloud Armor", "confidence": 0.94, "bbox": [210, 90, 330, 112]},
            {"text": "Internal resource", "confidence": 0.90, "bbox": [240, 220, 340, 242]},
        ]

        self.assertEqual(_infer_diagram_provider(lines), "gcp")
        proposals = _ocr_component_proposals(lines, (600, 400))
        internal = next(item for item in proposals if item["name"] == "Internal resource")
        self.assertEqual(internal["provider"], "gcp")
        self.assertEqual(internal["metadata"]["localizationMethod"], "inline_card")

    def test_stacked_ocr_lines_recompose_service_label(self) -> None:
        lines = [
            {"text": "Application", "confidence": 0.94, "bbox": [100, 100, 180, 112]},
            {"text": "Load", "confidence": 0.95, "bbox": [120, 114, 160, 126]},
            {"text": "Balancer", "confidence": 0.96, "bbox": [105, 128, 175, 140]},
        ]

        phrases = _stacked_ocr_phrases(lines)

        self.assertTrue(any(item["text"] == "Application Load Balancer" for item in phrases))
        self.assertTrue(all(item["semanticStackDepth"] >= 2 for item in phrases))

    def test_protocol_is_extracted_from_explicit_url_scheme(self) -> None:
        self.assertEqual(
            _normalize_protocol_text("Ha https://domainname.azurewebsites.net"),
            "HTTPS",
        )

    def test_reviewed_boundary_membership_recalculates_flow_crossings(self) -> None:
        architecture = {
            "components": [
                {"id": "internet", "name": "Internet", "type": "internet"},
                {"id": "api", "name": "API", "type": "api_gateway"},
                {"id": "db", "name": "Database", "type": "database"},
            ],
            "trustBoundaries": [
                {"id": "private", "name": "Private zone", "componentIds": ["api", "db"]}
            ],
            "flows": [
                {"id": "external", "from": "internet", "to": "api", "trustBoundary": False},
                {"id": "internal", "from": "api", "to": "db", "trustBoundary": True},
            ],
        }

        reconciled = _reconcile_trust_boundary_crossings(architecture)

        self.assertTrue(reconciled["flows"][0]["trustBoundary"])
        self.assertEqual(reconciled["flows"][0]["crossedBoundaryIds"], ["private"])
        self.assertFalse(reconciled["flows"][1]["trustBoundary"])
        self.assertEqual(reconciled["flows"][1]["crossedBoundaryIds"], [])
        self.assertFalse(architecture["flows"][0]["trustBoundary"])

    def test_nearby_ocr_line_is_associated_with_component(self) -> None:
        lines = [
            {
                "text": "Amazon RDS",
                "confidence": 0.91,
                "bbox": [85, 135, 155, 150],
                "engine": "tesseract",
            }
        ]

        match = match_component_label(lines, [100, 80, 140, 125])

        self.assertIsNotNone(match)
        self.assertEqual(match["text"], "Amazon RDS")

    def test_protocol_requires_explicit_ocr_text_near_flow(self) -> None:
        components = [
            {"id": "api", "bbox": [0, 0, 20, 20]},
            {"id": "db", "bbox": [100, 0, 120, 20]},
        ]
        flows = [{"id": "f1", "from": "api", "to": "db", "protocol": "unknown"}]
        lines = [
            {
                "text": "HTTPS",
                "confidence": 0.93,
                "bbox": [46, 2, 74, 16],
                "engine": "tesseract",
            }
        ]

        apply_protocol_evidence(flows, components, lines)

        self.assertEqual(flows[0]["protocol"], "HTTPS")
        self.assertEqual(flows[0]["protocolEvidence"]["engine"], "tesseract")

    def test_provider_requires_explicit_evidence(self) -> None:
        self.assertEqual(_infer_provider("database", "Relational Database"), "generic")
        self.assertEqual(_infer_provider("database", "Amazon RDS"), "aws")
        self.assertEqual(_infer_provider("identity_provider", "Microsoft Entra ID"), "azure")
        self.assertEqual(_infer_provider("compute", "Google Cloud Run"), "gcp")

    def test_ocr_label_cannot_override_conflicting_supervised_class(self) -> None:
        self.assertFalse(_ocr_label_is_compatible("database", "CDN"))
        self.assertTrue(_ocr_label_is_compatible("database", "Amazon RDS"))
        self.assertTrue(_ocr_label_is_compatible("compute", "Amazon SageMaker"))
        self.assertTrue(_ocr_label_is_compatible("user", "Customer"))

    def test_geometric_flows_require_review(self) -> None:
        components = [
            {"id": "internet", "type": "internet", "bbox": [0, 0, 20, 20]},
            {"id": "api", "type": "api_gateway", "bbox": [100, 0, 120, 20]},
        ]

        flows = _infer_flows(components)

        self.assertEqual(len(flows), 1)
        self.assertTrue(flows[0]["inferred"])
        self.assertEqual(flows[0]["reviewStatus"], "pending")
        self.assertTrue(flows[0]["trustBoundary"])
        self.assertEqual(flows[0]["evidence"], "layout_adjacency")

    def test_visual_line_and_rectangular_trust_zone_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "architecture.png"
            image = Image.new("RGB", (500, 220), "white")
            drawing = ImageDraw.Draw(image)
            drawing.rectangle((140, 25, 470, 195), outline="black", width=3)
            drawing.rectangle((20, 85, 70, 135), outline="black", width=3)
            drawing.rectangle((190, 85, 240, 135), outline="black", width=3)
            drawing.rectangle((350, 85, 400, 135), outline="black", width=3)
            drawing.line((70, 110, 190, 110), fill="black", width=4)
            drawing.line((240, 110, 350, 110), fill="black", width=4)
            image.save(image_path)

            components = [
                {"id": "internet", "type": "internet", "bbox": [20, 85, 70, 135]},
                {"id": "api", "type": "api_gateway", "bbox": [190, 85, 240, 135]},
                {"id": "db", "type": "database", "bbox": [350, 85, 400, 135]},
            ]
            boundaries = detect_trust_boundaries(image_path, components)
            flows, diagnostics = detect_flows(image_path, components, boundaries)

            self.assertTrue(any(set(boundary["componentIds"]) == {"api", "db"} for boundary in boundaries))
            external_flow = next(
                flow for flow in flows if flow["from"] == "internet" and flow["to"] == "api"
            )
            self.assertIn(external_flow["evidence"], {"detected_line", "pixel_line_support"})
            self.assertTrue(external_flow["trustBoundary"])
            self.assertGreaterEqual(diagnostics["associatedSegments"], 2)

    def test_visual_arrowhead_sets_flow_direction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "arrow.png"
            image = Image.new("RGB", (400, 190), "white")
            drawing = ImageDraw.Draw(image)
            drawing.rectangle((20, 70, 70, 120), outline="black", width=3)
            drawing.rectangle((300, 70, 350, 120), outline="black", width=3)
            drawing.line((70, 95, 300, 95), fill="black", width=3)
            drawing.line((300, 95, 289, 89), fill="black", width=3)
            drawing.line((300, 95, 289, 101), fill="black", width=3)
            image.save(image_path)
            components = [
                {"id": "compute", "type": "compute", "bbox": [20, 70, 70, 120]},
                {"id": "database", "type": "database", "bbox": [300, 70, 350, 120]},
            ]

            flows, _ = detect_flows(image_path, components)

            self.assertEqual(len(flows), 1)
            self.assertEqual((flows[0]["from"], flows[0]["to"]), ("compute", "database"))
            self.assertIn(flows[0]["directionEvidence"], {"visual_arrowhead", "supervised_arrowhead"})
            classifier = flows[0]["arrowheadScores"].get("classifier") or {}
            self.assertEqual(classifier.get("model"), "arrowhead-logistic")

    def test_segment_graph_connects_elbow_before_component_association(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "elbow-flow.png"
            image = Image.new("RGB", (420, 240), "white")
            drawing = ImageDraw.Draw(image)
            drawing.rectangle((20, 55, 70, 105), outline="black", width=3)
            drawing.rectangle((320, 145, 370, 195), outline="black", width=3)
            drawing.line((70, 80, 190, 80), fill="black", width=3)
            drawing.line((190, 80, 190, 170), fill="black", width=3)
            drawing.line((190, 170, 320, 170), fill="black", width=3)
            image.save(image_path)
            components = [
                {"id": "api", "type": "api_gateway", "bbox": [20, 55, 70, 105]},
                {"id": "db", "type": "database", "bbox": [320, 145, 370, 195]},
            ]

            flows, diagnostics = detect_flows(image_path, components)

            pair = next(flow for flow in flows if {flow["from"], flow["to"]} == {"api", "db"})
            self.assertEqual(pair["evidence"], "segment_graph")
            self.assertGreaterEqual(len(pair["pathPoints"]), 3)
            self.assertGreaterEqual(diagnostics["segmentGraph"]["paths"], 1)

    def test_fragmented_pixel_line_recovers_flow_with_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "fragmented-line.png"
            image = Image.new("RGB", (400, 190), "white")
            drawing = ImageDraw.Draw(image)
            drawing.rectangle((20, 70, 70, 120), outline="black", width=3)
            drawing.rectangle((300, 70, 350, 120), outline="black", width=3)
            drawing.line((70, 95, 170, 95), fill="black", width=3)
            drawing.line((194, 95, 300, 95), fill="black", width=3)
            image.save(image_path)
            components = [
                {"id": "api", "type": "api_gateway", "bbox": [20, 70, 70, 120]},
                {"id": "db", "type": "database", "bbox": [300, 70, 350, 120]},
            ]

            flows, diagnostics = detect_flows(image_path, components)

            self.assertEqual(len(flows), 1)
            self.assertEqual(flows[0]["evidence"], "pixel_line_support")
            self.assertEqual(len(flows[0]["pathPoints"]), 2)
            self.assertEqual(diagnostics["pixelRecoveredFlows"], 1)

    def test_direct_line_does_not_skip_an_intermediate_component(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "intermediate-component.png"
            image = Image.new("RGB", (440, 190), "white")
            drawing = ImageDraw.Draw(image)
            boxes = ((20, 70, 70, 120), (190, 70, 240, 120), (360, 70, 410, 120))
            for box in boxes:
                drawing.rectangle(box, outline="black", width=3)
            drawing.line((70, 95, 190, 95), fill="black", width=3)
            drawing.line((240, 95, 360, 95), fill="black", width=3)
            image.save(image_path)
            components = [
                {"id": "client", "type": "compute", "bbox": list(boxes[0])},
                {"id": "api", "type": "api_gateway", "bbox": list(boxes[1])},
                {"id": "db", "type": "database", "bbox": list(boxes[2])},
            ]

            flows, _ = detect_flows(image_path, components)
            pairs = {frozenset((flow["from"], flow["to"])) for flow in flows}

            self.assertNotIn(frozenset(("client", "db")), pairs)
            self.assertIn(frozenset(("client", "api")), pairs)
            self.assertIn(frozenset(("api", "db")), pairs)

    def test_boundary_crossing_is_derived_from_membership(self) -> None:
        boundaries = [{"id": "vpc", "componentIds": ["api", "db"]}]
        self.assertEqual(boundary_ids_crossed("internet", "api", boundaries), ["vpc"])
        self.assertEqual(boundary_ids_crossed("api", "db", boundaries), [])

    def test_diagram_augmentation_does_not_mirror_text(self) -> None:
        config = _augmentation_config("diagram")
        self.assertEqual(config["flipud"], 0.0)
        self.assertEqual(config["fliplr"], 0.0)
        self.assertEqual(config["mosaic"], 0.0)
        self.assertLessEqual(config["degrees"], 1.0)

    def test_training_manifest_resolves_images_and_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "images" / "train" / "diagram.jpg"
            label = root / "labels" / "train" / "diagram.txt"
            image.parent.mkdir(parents=True)
            label.parent.mkdir(parents=True)
            image.write_bytes(b"image")
            label.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            manifest = root / "train.txt"
            manifest.write_text(f"{image.as_posix()}\n", encoding="utf-8")

            self.assertEqual(_list_images(manifest), [image.resolve()])
            self.assertEqual(_label_for_image(image), label)


class UploadSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_png_is_verified_from_content(self) -> None:
        buffer = BytesIO()
        Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
        upload = _MemoryUpload(buffer.getvalue(), "image/png")

        result = await _read_validated_image(upload, max_size=2048)

        self.assertTrue(result.startswith(b"\x89PNG"))

    async def test_invalid_image_content_is_rejected(self) -> None:
        upload = _MemoryUpload(b"not an image", "image/png")

        with self.assertRaises(HTTPException) as context:
            await _read_validated_image(upload, max_size=2048)

        self.assertEqual(context.exception.status_code, 415)

    async def test_upload_stops_when_stream_exceeds_limit(self) -> None:
        upload = _MemoryUpload(b"0123456789", "image/png")

        with self.assertRaises(HTTPException) as context:
            await _read_validated_image(upload, max_size=8)

        self.assertEqual(context.exception.status_code, 413)


class _MemoryUpload:
    def __init__(self, content: bytes, content_type: str):
        self._content = BytesIO(content)
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        return self._content.read(size)


class ArchitectureValidationTests(unittest.TestCase):
    def test_unsupported_component_type_is_rejected(self) -> None:
        payload = {
            "components": [{"id": "mystery", "name": "Mystery", "type": "unknown_service"}],
            "flows": [],
        }

        with self.assertRaisesRegex(HTTPException, "Unsupported component type"):
            _validate_architecture_payload(payload)

    def test_component_count_is_bounded(self) -> None:
        payload = {
            "components": [
                {"id": f"api_{index}", "name": f"API {index}", "type": "api_gateway"}
                for index in range(201)
            ],
            "flows": [],
        }

        with self.assertRaisesRegex(HTTPException, "At most"):
            _validate_architecture_payload(payload)

    def test_boolean_confidence_is_rejected(self) -> None:
        payload = {
            "components": [{"id": "api", "name": "API", "type": "api_gateway", "confidence": True}],
            "flows": [],
        }

        with self.assertRaisesRegex(HTTPException, "Component confidence"):
            _validate_architecture_payload(payload)

    def test_duplicate_component_ids_are_rejected(self) -> None:
        payload = {
            "components": [
                {"id": "api", "name": "API one", "type": "api_gateway"},
                {"id": "api", "name": "API two", "type": "api_gateway"},
            ],
            "flows": [],
        }

        with self.assertRaisesRegex(HTTPException, "unique"):
            _validate_architecture_payload(payload)

    def test_invalid_bounding_box_is_rejected(self) -> None:
        payload = {
            "components": [
                {
                    "id": "api",
                    "name": "API",
                    "type": "api_gateway",
                    "bbox": [50, 10, 20, 40],
                }
            ],
            "flows": [],
        }

        with self.assertRaisesRegex(HTTPException, "bbox"):
            _validate_architecture_payload(payload)

    def test_invalid_flow_confidence_is_rejected(self) -> None:
        payload = {
            "components": [
                {"id": "api", "name": "API", "type": "api_gateway"},
                {"id": "db", "name": "Database", "type": "database"},
            ],
            "flows": [{"id": "f1", "from": "api", "to": "db", "confidence": 1.2}],
        }

        with self.assertRaisesRegex(HTTPException, "Flow confidence"):
            _validate_architecture_payload(payload)

    def test_unknown_trust_boundary_member_is_rejected(self) -> None:
        payload = {
            "components": [{"id": "api", "name": "API", "type": "api_gateway"}],
            "flows": [],
            "trustBoundaries": [
                {"id": "vpc", "name": "VPC", "componentIds": ["missing-component"]}
            ],
        }

        with self.assertRaisesRegex(HTTPException, "componentIds"):
            _validate_architecture_payload(payload)


class HumanReviewTests(unittest.TestCase):
    def test_readiness_reports_each_missing_dependency(self) -> None:
        readiness = _readiness_summary(
            {"available": False, "confidenceCalibration": {"available": False}},
            {"ready": False, "chunks": 0},
        )

        self.assertFalse(readiness["ready"])
        self.assertEqual(len(readiness["reasons"]), 3)

    def test_rag_document_ids_change_with_content(self) -> None:
        self.assertNotEqual(
            _doc_id("stride/test.md", 0, "first content"),
            _doc_id("stride/test.md", 0, "updated content"),
        )

    def test_rag_lexical_fallback_returns_grounded_sources(self) -> None:
        results = _query_lexical(["database", "tampering"], top_k=3)

        self.assertTrue(results)
        self.assertTrue(all(result.startswith("**[") for result in results))
        self.assertTrue(any("database" in result.lower() for result in results))

    def test_pdf_text_is_escaped_and_bounded(self) -> None:
        escaped = _safe("<b>unsafe & text</b>", limit=12)

        self.assertNotIn("<b>", escaped)
        self.assertIn("&lt;b&gt;", escaped)

    def test_threat_trace_links_rule_flow_boundary_and_rag_source(self) -> None:
        architecture = {
            "components": [
                {"id": "internet", "name": "Internet", "type": "internet"},
                {"id": "api", "name": "API", "type": "api_gateway"},
            ],
            "flows": [
                {
                    "id": "f1",
                    "from": "internet",
                    "to": "api",
                    "protocol": "unknown",
                    "trustBoundary": True,
                    "crossedBoundaryIds": ["edge"],
                }
            ],
        }
        catalog = _build_evidence_catalog(
            ["**[stride/spoofing.md] API identity**\nRequire strong authentication."]
        )
        threat = {
            "stride": "Spoofing",
            "source": "flow-rule",
            "ruleId": "internet-to-api",
            "componentId": "architecture",
        }

        trace = _trace_threat(threat, architecture, catalog)

        self.assertEqual(trace["flowIds"], ["f1"])
        self.assertEqual(trace["componentIds"], ["api", "internet"])
        self.assertEqual(trace["boundaryIds"], ["edge"])
        self.assertEqual(trace["ragSourceIds"], [catalog[0]["id"]])

    def test_rejected_ocr_label_is_exposed_for_human_review(self) -> None:
        source = {
            "components": [
                {
                    "id": "db",
                    "name": "Database",
                    "type": "database",
                    "confidence": 0.9,
                    "reviewStatus": "auto_accepted",
                    "ocrEvidence": {
                        "text": "CDN",
                        "confidence": 0.92,
                        "accepted": False,
                        "rejectionReason": "label_conflicts_with_supervised_class",
                    },
                }
            ],
            "flows": [],
        }
        analysis = analyze_architecture(source)

        response = _build_response(
            analysis,
            [],
            analysis["reportMarkdown"],
            {"approved": True, "score": 1.0, "issues": [], "criteria": {}},
            "yolo",
        )

        review_ids = {item["id"] for item in response["humanReviewItems"]}
        self.assertIn("ocr-db", review_ids)

    def test_normalization_preserves_detection_trace(self) -> None:
        architecture = normalize_architecture(
            {
                "name": "Detected",
                "detectedBy": "yolo",
                "detectorModel": "best.pt",
                "detectorMetadata": {"modelSha256": "abc"},
                "reviewRequired": True,
                "components": [
                    {
                        "id": "api",
                        "name": "API",
                        "type": "api_gateway",
                        "reviewStatus": "pending",
                    }
                ],
                "flows": [],
            }
        )

        self.assertEqual(architecture["detectedBy"], "yolo")
        self.assertEqual(architecture["detectorMetadata"]["modelSha256"], "abc")
        self.assertEqual(architecture["components"][0]["reviewStatus"], "pending")

    def test_normalization_preserves_flow_evidence(self) -> None:
        architecture = normalize_architecture(
            {
                "components": [
                    {"id": "internet", "name": "Internet", "type": "internet"},
                    {"id": "api", "name": "API", "type": "api_gateway"},
                ],
                "flows": [
                    {
                        "id": "f1",
                        "from": "internet",
                        "to": "api",
                        "protocol": "unknown",
                        "trustBoundary": True,
                        "evidence": "detected_line",
                        "directionEvidence": "semantic_source",
                        "crossedBoundaryIds": ["tb1"],
                    }
                ],
            }
        )

        flow = architecture["flows"][0]
        self.assertEqual(flow["evidence"], "detected_line")
        self.assertEqual(flow["crossedBoundaryIds"], ["tb1"])

    def test_stride_flags_unknown_protocol_at_trust_boundary(self) -> None:
        analysis = analyze_architecture(
            {
                "components": [
                    {"id": "internet", "name": "Internet", "type": "internet"},
                    {"id": "api", "name": "API", "type": "api_gateway"},
                ],
                "flows": [
                    {
                        "id": "f1",
                        "from": "internet",
                        "to": "api",
                        "protocol": "unknown",
                        "trustBoundary": True,
                    }
                ],
            }
        )

        rule_ids = {threat.get("ruleId") for threat in analysis["threats"]}
        self.assertIn("unknown-protocol-crosses-trust-boundary", rule_ids)

    def test_response_exposes_pending_component_and_inferred_flow(self) -> None:
        source = {
            "name": "Review test",
            "detectedBy": "yolo",
            "reviewedByHuman": False,
            "components": [
                {
                    "id": "internet",
                    "name": "Internet",
                    "type": "internet",
                    "confidence": 0.91,
                    "reviewStatus": "auto_accepted",
                },
                {
                    "id": "api",
                    "name": "API",
                    "type": "api_gateway",
                    "confidence": 0.58,
                    "reviewStatus": "pending",
                },
            ],
            "flows": [
                {
                    "id": "f1",
                    "from": "internet",
                    "to": "api",
                    "protocol": "HTTPS",
                    "inferred": True,
                    "confidence": 0.45,
                    "reviewStatus": "pending",
                }
            ],
        }
        analysis = analyze_architecture(source)

        response = _build_response(
            analysis,
            [],
            analysis["reportMarkdown"],
            {"approved": True, "score": 1.0, "issues": [], "criteria": {}},
            "yolo",
        )

        review_ids = {item["id"] for item in response["humanReviewItems"]}
        self.assertIn("api", review_ids)
        self.assertIn("f1", review_ids)
        self.assertTrue(response["pipeline"]["reviewRequired"])

    def test_deterministic_report_passes_local_grounding_gate(self) -> None:
        source = {
            "name": "Local report",
            "components": [
                {"id": "api", "name": "API", "type": "api_gateway", "confidence": 0.9}
            ],
            "flows": [],
        }
        analysis = analyze_architecture(source)

        validation = _validate_report_locally(
            analysis["reportMarkdown"],
            analysis["architecture"],
            analysis["threats"],
        )

        self.assertTrue(validation["approved"])
        self.assertEqual(validation["validator"], "deterministic_grounding_gate")

    def test_threats_include_security_references_and_management_defaults(self) -> None:
        analysis = analyze_architecture(
            {
                "components": [
                    {"id": "api", "name": "API", "type": "api_gateway", "confidence": 0.9}
                ],
                "flows": [],
            }
        )

        threat = analysis["threats"][0]
        frameworks = {reference["framework"] for reference in threat["securityReferences"]}
        self.assertEqual(threat["management"]["status"], "open")
        self.assertTrue({"CWE", "CAPEC", "OWASP", "MITRE ATT&CK"}.issubset(frameworks))

    def test_mitigation_decision_reduces_residual_risk_and_is_reported(self) -> None:
        source = {
            "components": [
                {"id": "api", "name": "API", "type": "api_gateway", "confidence": 0.9}
            ],
            "flows": [],
        }
        baseline = analyze_architecture(source)
        threat_id = baseline["threats"][0]["id"]
        source["threatManagement"] = {
            threat_id: {
                "status": "mitigated",
                "owner": "AppSec",
                "justification": "Control validated in staging.",
                "selectedCountermeasure": baseline["threats"][0]["countermeasures"][0],
            }
        }

        analysis = analyze_architecture(source)

        managed = next(threat for threat in analysis["threats"] if threat["id"] == threat_id)
        self.assertEqual(managed["management"]["owner"], "AppSec")
        self.assertLess(
            analysis["riskComparison"]["residual"]["value"],
            analysis["riskComparison"]["inherent"]["value"],
        )
        self.assertIn("## Mitigation plan", analysis["reportMarkdown"])
        self.assertIn("CWE-", analysis["reportMarkdown"])

    def test_invalid_management_status_falls_back_to_open(self) -> None:
        source = {
            "components": [{"id": "db", "name": "DB", "type": "database"}],
            "flows": [],
        }
        baseline = analyze_architecture(source)
        source["threatManagement"] = {
            baseline["threats"][0]["id"]: {"status": "deleted"}
        }

        analysis = analyze_architecture(source)

        self.assertEqual(analysis["threats"][0]["management"]["status"], "open")

    def test_pdf_report_is_generated_offline(self) -> None:
        from backend.pdf_report import generate_pdf

        analysis = analyze_architecture({
            "name": "PDF test",
            "components": [{"id": "api", "name": "API", "type": "api_gateway"}],
            "flows": [],
        })

        content = generate_pdf(analysis)

        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 3000)


if __name__ == "__main__":
    unittest.main()
