#!/usr/bin/env python3
"""Spike autorouting — paso 3: import SES headless via pcbnew (python del SISTEMA).

Uso:  /usr/bin/python3 02_import_ses.py <board.kicad_pcb> <in.ses> <out.kicad_pcb>

- Carga el board de DISCO (con el contorno del paso 1).
- Importa el .ses de Freerouting (ImportSpecctraSES, forma de 2 args).
- Guarda el board ruteado en out (SaveBoard).
- Reporta conteo de tracks/vías resultantes.
"""
import sys, os, time
import pcbnew


def counts(board):
    tracks = vias = 0
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias += 1
        else:
            tracks += 1
    return tracks, vias


def main():
    board_path, ses, out = sys.argv[1], sys.argv[2], sys.argv[3]
    board = pcbnew.LoadBoard(board_path)
    t_before, v_before = counts(board)
    t0 = time.time()
    ok = pcbnew.ImportSpecctraSES(board, ses)
    dt = time.time() - t0
    t_after, v_after = counts(board)
    if ok:
        pcbnew.SaveBoard(out, board)
    print(f"[import] ImportSpecctraSES ok={ok} t={dt:.2f}s")
    print(f"[import] tracks {t_before}->{t_after}  vias {v_before}->{v_after}")
    print(f"[import] guardado -> {out}" if ok else "[import] NO guardado (falló)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
