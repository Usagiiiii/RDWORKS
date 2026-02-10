import os
import tempfile
import subprocess
from typing import List, Tuple

from utils.tool_utils import _check_conversion_tool
from my_io.importers.import_dxf import import_dxf_by_layer

Pt = Tuple[float, float]
Path = List[Pt]


def _convert_dwg_to_dxf(dwg_path: str) -> str:
    tool = _check_conversion_tool("ODAFileConverter")
    if not tool:
        raise RuntimeError("需要安装 ODA File Converter，并配置到 PATH 或设置环境变量 LITEGCODE_ODAFILECONVERTER_PATH")

    input_dir = os.path.dirname(dwg_path)
    filename = os.path.basename(dwg_path)

    with tempfile.TemporaryDirectory() as out_dir:
        cmd = [
            tool,
            input_dir,
            out_dir,
            "ACAD2013",
            "DXF",
            "0",
            "1",
            filename,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"DWG 转换失败: {result.stderr.strip()}")

        dxf_name = os.path.splitext(filename)[0] + ".dxf"
        converted = os.path.join(out_dir, dxf_name)
        if not os.path.exists(converted):
            raise RuntimeError("DWG 转换失败: 未生成 DXF 文件")

        # Copy to a persistent temp file for downstream import
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            with open(converted, "rb") as f:
                tmp.write(f.read())
            return tmp.name


def import_dwg(path: str, tol_mm: float = 0.2, close_gap_mm: float = 0.1, unit_scale: float = None):
    dxf_path = None
    try:
        dxf_path = _convert_dwg_to_dxf(path)
        return import_dxf_by_layer(dxf_path, tol_mm=tol_mm, close_gap_mm=close_gap_mm, unit_scale=unit_scale)
    finally:
        if dxf_path and os.path.exists(dxf_path):
            try:
                os.unlink(dxf_path)
            except Exception:
                pass
