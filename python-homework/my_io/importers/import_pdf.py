from typing import List, Tuple
import fitz

Pt = Tuple[float, float]
Path = List[Pt]


def import_pdf_or_ai(path: str) -> List[Path]:
    """导入PDF文件（复用原函数名，专注处理PDF）"""
    try:
        import fitz
    except ImportError:
        raise RuntimeError('需要安装 PyMuPDF: pip install pymupdf')

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise RuntimeError(f'无法打开文件: {str(e)}')

    out = []
    for page in doc:
        try:
            drawings = page.get_drawings()
            for d in drawings:
                pts = []
                for item in d['items']:
                    if item[0] == 'l':  # 直线
                        _, p1, p2 = item
                        if not pts:
                            pts.append((p1.x, p1.y))
                        pts.append((p2.x, p2.y))
                if len(pts) >= 2:
                    out.append(pts)
        except Exception:
            continue

    if not out:
        raise RuntimeError("未从PDF文件中提取到矢量路径")

    return out