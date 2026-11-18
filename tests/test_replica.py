"""Prueba: la réplica debe reproducir la Tabla 3 (P2P) del artículo. Ejecutar: python -m pytest tests"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ocpm_metrics import load_jsonocel, monitor  # noqa: E402
from replicate import P2P_LOGS, P2P_OPGS, P2P_REALITY  # noqa: E402


def test_tabla3_p2p():
    for prob, opg in P2P_OPGS.items():
        for i, lg in enumerate(P2P_LOGS):
            log = load_jsonocel(os.path.join(ROOT, "data", "p2p", lg + ".jsonocel"))
            occ, _ = monitor(log, opg)
            assert occ == P2P_REALITY[prob][i], f"{prob} en {lg}"


if __name__ == "__main__":
    test_tabla3_p2p()
    print("OK: Tabla 3 reproducida (9/9).")


def test_estabilidad(repeticiones=5):
    """El cálculo es determinista: varias ejecuciones deben dar exactamente los mismos valores."""
    resultados = []
    for _ in range(repeticiones):
        fila = []
        for opg in P2P_OPGS.values():
            for lg in P2P_LOGS:
                log = load_jsonocel(os.path.join(ROOT, "data", "p2p", lg + ".jsonocel"))
                fila.append(monitor(log, opg))
        resultados.append(fila)
    assert all(r == resultados[0] for r in resultados)


if __name__ == "__main__":
    test_estabilidad()
    print("OK: 5 ejecuciones con resultados idénticos.")
