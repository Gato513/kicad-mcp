#!/usr/bin/env python3
"""Spike autorouting — paso 1: export DSN headless via pcbnew (python del SISTEMA).

Uso:  /usr/bin/python3 01_export_dsn.py <src.kicad_pcb> <out.dsn> [margin_mm]

- Carga el board de DISCO (LoadBoard).
- Si NO hay contorno Edge.Cuts, dibuja un rectángulo = bbox(items)+margen y
  GUARDA el board (para que el contorno persista y el import posterior calce).
- Exporta Specctra DSN con la forma de 2 args (headless, sin GetBoard()).

NO es dependencia del proyecto: corre con el python del sistema que trae KiCad,
como proceso hijo (igual que kicad-cli). Ver informe.md §caminos.
"""
import sys, os, time
import pcbnew

FROM_MM = pcbnew.FromMM  # mm -> nm (int)


def has_outline(board) -> bool:
    edge = pcbnew.Edge_Cuts
    for d in board.GetDrawings():
        try:
            if d.GetLayer() == edge:
                return True
        except Exception:
            continue
    return False


def draw_outline(board, margin_mm: float):
    bb = board.ComputeBoundingBox(False)  # False = incluye todo, no solo Edge.Cuts
    m = FROM_MM(margin_mm)
    x0, y0 = bb.GetX() - m, bb.GetY() - m
    x1, y1 = bb.GetRight() + m, bb.GetBottom() + m
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(pcbnew.VECTOR2I(pts[i][0], pts[i][1]))
        seg.SetEnd(pcbnew.VECTOR2I(pts[(i + 1) % 4][0], pts[(i + 1) % 4][1]))
        seg.SetWidth(FROM_MM(0.1))
        board.Add(seg)
    return (x1 - x0) / 1e6, (y1 - y0) / 1e6


def main():
    src, out = sys.argv[1], sys.argv[2]
    margin = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
    board = pcbnew.LoadBoard(src)
    if has_outline(board):
        print(f"[export] contorno Edge.Cuts ya presente")
    else:
        w, h = draw_outline(board, margin)
        pcbnew.SaveBoard(src, board)  # persiste el contorno en el mismo archivo
        print(f"[export] contorno dibujado {w:.1f}x{h:.1f}mm (margen {margin}mm) y guardado")
    t0 = time.time()
    ok = pcbnew.ExportSpecctraDSN(board, out)
    dt = time.time() - t0
    size = os.path.getsize(out) if os.path.exists(out) else 0
    print(f"[export] ExportSpecctraDSN ok={ok} t={dt:.2f}s size={size}B -> {out}")
    sys.exit(0 if ok and size > 0 else 1)


if __name__ == "__main__":
    main()
