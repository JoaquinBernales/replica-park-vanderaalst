"""
Réplica de la Sección 7.1 de Park & van der Aalst (2025), Computers in Industry 164, 104170.

Experimento 1  – Tabla 3: monitoreo de problemas operativos en el proceso P2P (compras).
Experimento 1b – Tabla 2: monitoreo en el proceso de manufactura (secundario).
Experimento 2  – Validación cuantitativa: exactitud, precisión, recall y F1 frente a la
                 columna "Reality" que reporta el artículo.
Experimento 3  – Sensibilidad al umbral (análogo a la Fig. 14 del artículo, aplicado a P2P).
Experimento 4  – Tabla 4: valores de las métricas en el log real BPI Challenge 2017.

Uso:
    python src/replicate.py --data data --out results
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocpm_metrics import Edge, load_jsonocel, monitor  # noqa: E402

# --------------------------------------------------------------------------- #
#  OPGs tal como aparecen en el artículo (Fig. 12 y Fig. 10)                   #
# --------------------------------------------------------------------------- #
# Nota: en la Fig. 12(a) el OPG de "Clearance of MIs" está dibujado sobre la
# actividad "plan goods issue", pero esa actividad nunca involucra facturas en los
# logs públicos (métrica = 0 en todos). El texto del artículo define el problema
# sobre "the event of clearing an invoice", por lo que se usa "Clear Invoice".
P2P_OPGS = {
    "Clearance of MIs":           [Edge("h-cardinality", "Clear Invoice", ">", 0, ot="INVOICE", k=1)],
    "Excessive materials per PO": [Edge("freq_avg", "Create Purchase Order", ">=", 5, ot="MATERIAL")],
    "Delayed POC":                [Edge("sojourn_avg", "Create Purchase Order", ">=", 3)],
}
P2P_LOGS = ["p2p-log1", "p2p-log2", "p2p-log3"]
P2P_REALITY = {  # Tabla 3 del artículo (columna "Reality")
    "Clearance of MIs":           [True, True, False],
    "Excessive materials per PO": [False, False, True],
    "Delayed POC":                [False, False, True],
}

PROD_OPGS = {
    "Bypassing PRA":                [Edge("non-exist", "Approve Purchase Requisition", ">", 0, ot="PURCHREQ")],
    "Absent reservation for PRA":   [Edge("absent", "Approve Purchase Requisition", "<", 0.9, ot="RESERVATION")],
    "Excessive reservation per PO": [Edge("freq_avg", "Create Production Order", ">", 1, ot="RESERVATION")],
    "Delayed POR":                  [Edge("sojourn_avg", "Release Purchase Order", ">=", 15)],
}
PROD_LOGS = ["log1", "log2", "log3"]
PROD_REALITY = {  # Tabla 2 del artículo (columna "Reality")
    "Bypassing PRA":                [False, True, True],
    "Absent reservation for PRA":   [True, True, True],
    "Excessive reservation per PO": [True, True, True],
    "Delayed POR":                  [False, True, False],
}


def mark(b: bool) -> str:
    return "✓" if b else "✗"


def run_table(name, opgs, logs, reality, folder, out_dir):
    rows, pairs = [], []
    t0 = time.perf_counter()
    loaded = {lg: load_jsonocel(os.path.join(folder, lg + ".jsonocel")) for lg in logs}
    t_load = time.perf_counter() - t0
    t0 = time.perf_counter()
    for prob, opg in opgs.items():
        for i, lg in enumerate(logs):
            occ, vals = monitor(loaded[lg], opg)
            real = reality[prob][i]
            pairs.append((real, occ))
            rows.append({
                "problema": prob, "log": lg,
                "valor_metrica": round(vals[0], 4),
                "umbral": f"{opg[0].op} {opg[0].threshold}",
                "reality_paper": mark(real), "monitoreo_replica": mark(occ),
                "coincide": "sí" if real == occ else "no",
            })
    t_mon = time.perf_counter() - t0

    path = os.path.join(out_dir, f"{name}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows, pairs, t_load, t_mon


def scores(pairs):
    tp = sum(1 for r, p in pairs if r and p)
    tn = sum(1 for r, p in pairs if not r and not p)
    fp = sum(1 for r, p in pairs if not r and p)
    fn = sum(1 for r, p in pairs if r and not p)
    n = len(pairs)
    acc = (tp + tn) / n if n else 0
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return dict(n=n, TP=tp, TN=tn, FP=fp, FN=fn, exactitud=acc, precision=prec, recall=rec, f1=f1)


def sensitivity(folder, out_dir, fig_dir):
    """Barre el umbral de cada problema P2P y registra en qué logs se detecta."""
    sweeps = {
        "Clearance of MIs":           ("h-cardinality", "Clear Invoice", ">", "INVOICE", [i / 10 for i in range(0, 10)]),
        "Excessive materials per PO": ("freq_avg", "Create Purchase Order", ">=", "MATERIAL", [1, 2, 3, 4, 5, 6, 7]),
        "Delayed POC":                ("sojourn_avg", "Create Purchase Order", ">=", None, [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6]),
    }
    logs = {lg: load_jsonocel(os.path.join(folder, lg + ".jsonocel")) for lg in P2P_LOGS}
    rows = []
    for prob, (metric, act, op, ot, ths) in sweeps.items():
        for th in ths:
            det = [monitor(logs[lg], [Edge(metric, act, op, th, ot=ot)])[0] for lg in P2P_LOGS]
            rows.append({"problema": prob, "umbral": th, **{lg: int(d) for lg, d in zip(P2P_LOGS, det)},
                         "n_logs_detectados": sum(det)})
    with open(os.path.join(out_dir, "sensibilidad_umbral_p2p.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib no disponible: se omite la figura de sensibilidad.")
        return rows
    paper_th = {"Clearance of MIs": 0, "Excessive materials per PO": 5, "Delayed POC": 3}
    units = {"Clearance of MIs": "umbral (proporción)", "Excessive materials per PO": "umbral (materiales por OC)",
             "Delayed POC": "umbral (días)"}
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, prob in zip(axes, sweeps):
        r = [x for x in rows if x["problema"] == prob]
        ax.plot([x["umbral"] for x in r], [x["n_logs_detectados"] for x in r], marker="o", color="#1f5fa8")
        ax.axvline(paper_th[prob], ls="--", color="#c0392b", lw=1)
        ax.text(paper_th[prob], 3.05, " umbral del artículo", color="#c0392b", fontsize=8, va="bottom")
        ax.set_title(prob, fontsize=10)
        ax.set_xlabel(units[prob], fontsize=9)
        ax.set_ylim(-0.2, 3.5)
        ax.set_yticks([0, 1, 2, 3])
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("n.º de logs donde ocurre")
    fig.suptitle("Sensibilidad al umbral – proceso P2P (3 logs)", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(fig_dir, "sensibilidad_umbral_p2p.png"), dpi=150)
    plt.close(fig)
    return rows


def table4_bpi2017(csv_path, out_dir):
    """Experimento 4 – Tabla 4: valores de las métricas sobre el log real BPI Challenge 2017."""
    from datetime import timedelta
    from ocpm_metrics import (load_bpi2017_csv, exist, precede, h_cardinality, flow_avg,
                              sojourn_avg, sync_avg, pool_avg, ready_avg)
    t0 = time.perf_counter()
    L = load_bpi2017_csv(csv_path)
    t_load = time.perf_counter() - t0
    CA, APF = "Cancel application", "Assess potential fraud"
    d = lambda days, h, m, s: timedelta(days=days, hours=h, minutes=m, seconds=s).total_seconds()
    # (problema, valor del artículo, función que calcula la réplica, es_tiempo)
    spec = [
        ("Existence of CA",                 0.3310, lambda: exist(L, "APPLICATION", CA), False),
        ("APF precedes CA",                 0.6690, lambda: precede(L, "APPLICATION", APF, CA), False),
        ("CA with multiple offers",         0.2450, lambda: h_cardinality(L, "OFFER", CA, 1), False),
        ("High flow time of CA",            d(27, 14, 21, 49), lambda: flow_avg(L, CA).total_seconds(), True),
        ("High sojourn time of CA",         d(24, 23, 9, 35),  lambda: sojourn_avg(L, CA).total_seconds(), True),
        ("High sync time of CA w.r.t. Offer",    d(2, 0, 23, 45),  lambda: sync_avg(L, CA).total_seconds(), True),
        ("High pooling time of CA w.r.t. Offer", d(1, 17, 10, 17), lambda: pool_avg(L, "OFFER", CA).total_seconds(), True),
        ("High readiness time of CA w.r.t. Offer", d(0, 0, 25, 44), lambda: ready_avg(L, "OFFER", CA).total_seconds(), True),
    ]
    fmt = lambda v, is_t: str(timedelta(seconds=round(v))) if is_t else f"{v:.4f}"
    rows = []
    t0 = time.perf_counter()
    for name, paper, fn, is_t in spec:
        rep = fn()
        diff = (rep - paper) / paper * 100 if paper else 0.0
        rows.append({"problema": name, "valor_paper": fmt(paper, is_t), "valor_replica": fmt(rep, is_t),
                     "diferencia_%": round(diff, 2)})
    t_calc = time.perf_counter() - t0
    with open(os.path.join(out_dir, "tabla4_bpi2017.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nTABLA 4 – BPI Challenge 2017 ({len(L.events)} eventos, {len(L.obj_type)} objetos; "
          f"carga {t_load:.1f}s, cálculo {t_calc:.1f}s)")
    print(f"{'Problema':40} {'Paper':>22} {'Réplica':>22} {'Dif. %':>8}")
    for r in rows:
        print(f"{r['problema']:40} {r['valor_paper']:>22} {r['valor_replica']:>22} {r['diferencia_%']:>8}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fig_dir = os.path.join(a.out, "figuras")
    os.makedirs(fig_dir, exist_ok=True)

    # Experimento 1 – P2P (Tabla 3)
    rows3, pairs3, tl3, tm3 = run_table("tabla3_p2p", P2P_OPGS, P2P_LOGS, P2P_REALITY,
                                        os.path.join(a.data, "p2p"), a.out)
    # Experimento 1b – Manufactura (Tabla 2)
    rows2, pairs2, tl2, tm2 = run_table("tabla2_manufactura", PROD_OPGS, PROD_LOGS, PROD_REALITY,
                                        os.path.join(a.data, "production"), a.out)
    # Experimento 2 – métricas de validación
    s3, s2 = scores(pairs3), scores(pairs2)
    with open(os.path.join(a.out, "metricas_validacion.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["caso", *s3.keys(), "t_carga_s", "t_monitoreo_s"])
        w.writeheader()
        w.writerow({"caso": "P2P (Tabla 3)", **s3, "t_carga_s": round(tl3, 3), "t_monitoreo_s": round(tm3, 3)})
        w.writerow({"caso": "Manufactura (Tabla 2)", **s2, "t_carga_s": round(tl2, 3), "t_monitoreo_s": round(tm2, 3)})
    # Experimento 3 – sensibilidad
    sensitivity(os.path.join(a.data, "p2p"), a.out, fig_dir)

    # Consola
    for title, rows, s in [("TABLA 3 – P2P", rows3, s3), ("TABLA 2 – Manufactura", rows2, s2)]:
        print(f"\n{title}")
        print(f"{'Problema':30} {'Log':10} {'Métrica':>10} {'Umbral':>8}  Paper  Réplica")
        for r in rows:
            print(f"{r['problema']:30} {r['log']:10} {r['valor_metrica']:>10} {r['umbral']:>8}"
                  f"    {r['reality_paper']}      {r['monitoreo_replica']}")
        print(f"  -> coincidencias {s['TP'] + s['TN']}/{s['n']} | exactitud={s['exactitud']:.2f} "
              f"precisión={s['precision']:.2f} recall={s['recall']:.2f} F1={s['f1']:.2f}")

    # Experimento 4 – caso real (opcional: requiere data/bpi2017/BPI2017-Final.csv)
    bpi = os.path.join(a.data, "bpi2017", "BPI2017-Final.csv")
    if os.path.exists(bpi):
        table4_bpi2017(bpi, a.out)
    else:
        print(f"\n(Se omite la Tabla 4: no se encontró {bpi}. Ejecuta data/descargar_datos.py)")
    print(f"\nResultados guardados en: {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
