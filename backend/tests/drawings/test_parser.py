"""Tests for the DXF drawing parser."""

from __future__ import annotations

import tempfile
from pathlib import Path

import ezdxf
import pytest

from app.data.schemas import ConfidenceLevel, DimensionType
from app.drawings.parser import DrawingParser


@pytest.fixture
def simple_dxf() -> Path:
    """Create a minimal DXF file with a few dimension and text entities."""
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()

    # add_linear_dim returns DimStyleOverride; call .render() to commit entity
    override = msp.add_linear_dim(base=(0, 5), p1=(0, 0), p2=(33, 0), dimstyle="Standard")
    override.render()
    # Set actual_measurement on the underlying DIMENSION entity
    dim_entity = override.dimension
    dim_entity.dxf.actual_measurement = 33.0
    dim_entity.dxf.text = "33.0"

    # Add diameter dimension
    override2 = msp.add_linear_dim(base=(0, -5), p1=(0, 0), p2=(6, 0), dimstyle="Standard")
    override2.render()
    dim2_entity = override2.dimension
    dim2_entity.dxf.actual_measurement = 6.0
    dim2_entity.dxf.text = "⌀6.0"

    # Add text entities (title block style)
    msp.add_text("材料: 10B21", dxfattribs={"insert": (200, 10), "height": 3.5})
    msp.add_text("比例: 1:1", dxfattribs={"insert": (200, 20), "height": 3.5})
    msp.add_text("图号: 18149-D6", dxfattribs={"insert": (200, 30), "height": 3.5})

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        path = Path(f.name)
    doc.saveas(str(path))
    return path


def test_parser_returns_parsed_drawing(simple_dxf: Path) -> None:
    parser = DrawingParser()
    result = parser.parse(simple_dxf)
    assert result.file_format == "dxf"
    assert result.entity_count > 0


def test_parser_extracts_dimensions(simple_dxf: Path) -> None:
    parser = DrawingParser()
    result = parser.parse(simple_dxf)
    values = [d.value for d in result.dimensions]
    assert 33.0 in values


def test_parser_detects_diameter_dimension(simple_dxf: Path) -> None:
    parser = DrawingParser()
    result = parser.parse(simple_dxf)
    dia_dims = [d for d in result.dimensions if d.dimension_type == DimensionType.diameter]
    assert len(dia_dims) >= 1
    assert dia_dims[0].value == 6.0


def test_parser_extracts_title_block_material(simple_dxf: Path) -> None:
    parser = DrawingParser()
    result = parser.parse(simple_dxf)
    assert result.title_block.material == "10B21"


def test_parser_extracts_title_block_scale(simple_dxf: Path) -> None:
    parser = DrawingParser()
    result = parser.parse(simple_dxf)
    assert result.title_block.scale == "1:1"


def test_parser_missing_file_raises_error() -> None:
    parser = DrawingParser()
    with pytest.raises(FileNotFoundError):
        parser.parse("/nonexistent/path/drawing.dxf")


def test_parser_layer_names_extracted(simple_dxf: Path) -> None:
    parser = DrawingParser()
    result = parser.parse(simple_dxf)
    assert "0" in result.layer_names  # default layer always present


def test_extract_all_text(simple_dxf: Path) -> None:
    parser = DrawingParser()
    texts = parser.extract_all_text(simple_dxf)
    assert any("10B21" in t for t in texts)
