"""
Métricas de comportamiento centradas en objetos (Park & van der Aalst, 2025).

Implementación en Python puro (sin pm4py ni ocpa) de las definiciones de la
Sección 5 del artículo:

    Park, G., & van der Aalst, W. M. P. (2025). Operational process monitoring:
    An object-centric approach. Computers in Industry, 164, 104170.
    https://doi.org/10.1016/j.compind.2024.104170

Se implementan las métricas que usan los casos de uso de la Sección 7.1:
  - Def. 4  exist / non-exist                    (ocurrencia)
  - Def. 6  absent / present / h-cardinality_k   (participación de objetos)
  - Def. 8  freq_avg, flow, sojourn, sync         (rendimiento)
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
#  Carga del registro de eventos centrado en objetos (OCEL 1.0, formato JSON)  #
# --------------------------------------------------------------------------- #
@dataclass
class Event:
    eid: str
    activity: str
    time: datetime
    objects: List[str]


@dataclass
class OCEL:
    events: List[Event]
    obj_type: Dict[str, str]                       # objeto -> tipo
    seq: Dict[str, List[Event]] = field(default_factory=dict)  # σ(o)

    @property
    def activities(self) -> set:
        return {e.activity for e in self.events}

    def objects_of(self, ot: str) -> List[str]:
        return [o for o, t in self.obj_type.items() if t == ot]

    def events_of(self, act: str) -> List[Event]:
        return [e for e in self.events if e.activity == act]

    def objs(self, e: Event, ot: str) -> List[str]:
        return [o for o in e.objects if self.obj_type.get(o) == ot]


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_jsonocel(path: str) -> OCEL:
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    obj_type = {oid: o["ocel:type"] for oid, o in d["ocel:objects"].items()}
    events = [
        Event(eid, e["ocel:activity"], _parse_ts(e["ocel:timestamp"]), list(e["ocel:omap"]))
        for eid, e in d["ocel:events"].items()
    ]
    # orden total: tiempo y, ante empate, id del evento (orden de registro)
    events.sort(key=lambda e: (e.time, _num(e.eid)))
    seq: Dict[str, List[Event]] = defaultdict(list)
    for e in events:
        for o in e.objects:
            seq[o].append(e)
    return OCEL(events, obj_type, dict(seq))


def _num(s: str):
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else s


# --------------------------------------------------------------------------- #
#  Def. 4 – Métricas de ocurrencia                                             #
# --------------------------------------------------------------------------- #
def exist(log: OCEL, ot: str, act: str) -> float:
    """Proporción de objetos de tipo ot en cuyo ciclo de vida ocurre act."""
    objs = log.objects_of(ot)
    if not objs:
        return 0.0
    hit = sum(1 for o in objs if any(e.activity == act for e in log.seq.get(o, [])))
    return hit / len(objs)


def non_exist(log: OCEL, ot: str, act: str) -> float:
    """Proporción de objetos de tipo ot en cuyo ciclo de vida NO ocurre act."""
    return 1.0 - exist(log, ot, act) if log.objects_of(ot) else 0.0


# --------------------------------------------------------------------------- #
#  Def. 6 – Métricas de participación de objetos                               #
# --------------------------------------------------------------------------- #
def absent(log: OCEL, ot: str, act: str) -> float:
    evs = log.events_of(act)
    return sum(1 for e in evs if not log.objs(e, ot)) / len(evs) if evs else 0.0


def present(log: OCEL, ot: str, act: str) -> float:
    evs = log.events_of(act)
    return sum(1 for e in evs if log.objs(e, ot)) / len(evs) if evs else 0.0


def h_cardinality(log: OCEL, ot: str, act: str, k: int = 1) -> float:
    """Proporción de eventos act con MÁS de k objetos de tipo ot."""
    evs = log.events_of(act)
    return sum(1 for e in evs if len(log.objs(e, ot)) > k) / len(evs) if evs else 0.0


# --------------------------------------------------------------------------- #
#  Def. 7 y 8 – Relación de habilitación y métricas de rendimiento             #
# --------------------------------------------------------------------------- #
def _positions(log: OCEL) -> Dict:
    pos = getattr(log, "_pos", None)
    if pos is None:
        pos = {(o, id(e)): i for o, s in log.seq.items() for i, e in enumerate(s)}
        log._pos = pos
    return pos


def enabling_events(log: OCEL, e: Event) -> List[Event]:
    """rel(e) (Def. 7): eventos que preceden directamente a e en la secuencia de algún objeto."""
    pos = _positions(log)
    rel = {}
    for o in e.objects:
        i = pos[(o, id(e))]
        if i >= 1:
            prev = log.seq[o][i - 1]
            rel[prev.eid] = prev
    return list(rel.values())


def freq_avg(log: OCEL, ot: str, act: str) -> float:
    """Promedio de objetos de tipo ot por evento act."""
    evs = log.events_of(act)
    return mean(len(log.objs(e, ot)) for e in evs) if evs else 0.0


def _perf(log: OCEL, act: str, kind: str) -> Optional[timedelta]:
    vals = []
    for e in log.events_of(act):
        rel = enabling_events(log, e)
        if not rel:
            continue
        ts = [x.time for x in rel]
        if kind == "flow":
            v = e.time - min(ts)
        elif kind == "sojourn":
            v = e.time - max(ts)
        elif kind == "sync":
            v = max(ts) - min(ts)
        else:
            raise ValueError(kind)
        vals.append(v.total_seconds())
    return timedelta(seconds=mean(vals)) if vals else None


def flow_avg(log, act):    return _perf(log, act, "flow")
def sojourn_avg(log, act): return _perf(log, act, "sojourn")
def sync_avg(log, act):    return _perf(log, act, "sync")


def _perf_ot(log: OCEL, ot: str, act: str, kind: str) -> Optional[timedelta]:
    """pool / lag / ready (Def. 8): usan T'_e = habilitantes que involucran objetos de tipo ot."""
    vals = []
    for e in log.events_of(act):
        rel = enabling_events(log, e)
        rel_ot = [x for x in rel if any(log.obj_type.get(o) == ot for o in x.objects)]
        if not rel or not rel_ot:
            continue
        t_all = [x.time for x in rel]
        t_ot = [x.time for x in rel_ot]
        if kind == "pool":
            v = max(t_ot) - min(t_ot)
        elif kind == "lag":
            v = max(t_ot) - min(t_all)
        elif kind == "ready":
            v = max(t_all) - max(t_ot)
        else:
            raise ValueError(kind)
        vals.append(v.total_seconds())
    return timedelta(seconds=mean(vals)) if vals else None


def pool_avg(log, ot, act):  return _perf_ot(log, ot, act, "pool")
def lag_avg(log, ot, act):   return _perf_ot(log, ot, act, "lag")
def ready_avg(log, ot, act): return _perf_ot(log, ot, act, "ready")


# --------------------------------------------------------------------------- #
#  Def. 5 – Relación de orden                                                  #
# --------------------------------------------------------------------------- #
def precede(log: OCEL, ot: str, a: str, b: str) -> float:
    """Proporción de objetos ot donde, si ocurre b, a ocurre antes que b."""
    objs = log.objects_of(ot)
    ok = 0
    for o in objs:
        acts = [e.activity for e in log.seq.get(o, [])]
        if b not in acts:
            ok += 1
            continue
        first_a = acts.index(a) if a in acts else None
        last_b = len(acts) - 1 - acts[::-1].index(b)
        if first_a is not None and first_a < last_b:
            ok += 1
    return ok / len(objs) if objs else 0.0


# --------------------------------------------------------------------------- #
#  Carga del log BPI Challenge 2017 en formato CSV centrado en objetos         #
#  (archivo BPI2017-Final.csv publicado por los autores)                       #
# --------------------------------------------------------------------------- #
def load_bpi2017_csv(path: str) -> OCEL:
    import ast
    import csv

    events, obj_type = [], {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            objs = []
            for col, typ in (("application", "APPLICATION"), ("offer", "OFFER")):
                raw = (row.get(col) or "").strip()
                if raw.startswith("["):
                    for o in ast.literal_eval(raw):
                        objs.append(o)
                        obj_type[o] = typ
            t = datetime.strptime(row["event_timestamp"], "%Y/%m/%d %H:%M:%S.%f")
            events.append(Event(row["event_id"], row["event_activity"], t, objs))
    events.sort(key=lambda e: (e.time, _num(e.eid)))
    seq: Dict[str, List[Event]] = defaultdict(list)
    for e in events:
        for o in e.objects:
            seq[o].append(e)
    return OCEL(events, obj_type, dict(seq))


# --------------------------------------------------------------------------- #
#  Def. 9-11 – Grafo de problema operativo (OPG) y monitoreo                   #
# --------------------------------------------------------------------------- #
OPS = {
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "=": lambda a, b: a == b,
}


@dataclass
class Edge:
    metric: str            # nombre de la métrica
    act: str               # actividad
    op: str                # operador relacional
    threshold: float       # umbral (para tiempos: en días)
    ot: Optional[str] = None
    k: int = 1


def eval_edge(log: OCEL, ed: Edge):
    m = ed.metric
    if m == "exist":           v = exist(log, ed.ot, ed.act)
    elif m == "non-exist":     v = non_exist(log, ed.ot, ed.act)
    elif m == "absent":        v = absent(log, ed.ot, ed.act)
    elif m == "present":       v = present(log, ed.ot, ed.act)
    elif m == "h-cardinality": v = h_cardinality(log, ed.ot, ed.act, ed.k)
    elif m == "freq_avg":      v = freq_avg(log, ed.ot, ed.act)
    elif m in ("sojourn_avg", "flow_avg", "sync_avg"):
        td = {"sojourn_avg": sojourn_avg, "flow_avg": flow_avg, "sync_avg": sync_avg}[m](log, ed.act)
        v = td.total_seconds() / 86400 if td is not None else 0.0   # en días
    else:
        raise ValueError(m)
    return v, OPS[ed.op](v, ed.threshold)


def monitor(log: OCEL, opg: List[Edge]):
    """mon(EL, opg) = True si TODAS las aristas del OPG se cumplen (Def. 10-11)."""
    results = [eval_edge(log, ed) for ed in opg]
    return all(ok for _, ok in results), [v for v, _ in results]
