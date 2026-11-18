"""
Descarga los registros de eventos publicados por los autores en
https://github.com/gyunamister/proact (commit fijo para que la réplica sea exacta).

Uso:  python data/descargar_datos.py
"""
import os
import urllib.request
import zipfile

COMMIT = "28c453662c18d26863697910bbf06e2d4f826d3e"
BASE = f"https://raw.githubusercontent.com/gyunamister/proact/{COMMIT}/samples/logs"
FILES = {
    "p2p": ["p2p-log1.jsonocel", "p2p-log2.jsonocel", "p2p-log3.jsonocel"],
    "production": ["log1.jsonocel", "log2.jsonocel", "log3.jsonocel"],
    "bpi2017": ["BPI2017-OCEL.zip"],
}

here = os.path.dirname(os.path.abspath(__file__))
for folder, names in FILES.items():
    os.makedirs(os.path.join(here, folder), exist_ok=True)
    for n in names:
        dst = os.path.join(here, folder, n)
        if not os.path.exists(dst):
            url = f"{BASE}/{folder}/{n}"
            print("descargando", url)
            urllib.request.urlretrieve(url, dst)
        else:
            print("ya existe:", dst)
        if n.endswith(".zip"):
            with zipfile.ZipFile(dst) as z:
                for member in z.namelist():
                    if member.endswith(".csv") and not member.startswith("__MACOSX"):
                        z.extract(member, os.path.join(here, folder))
                        print("extraído:", member)
print("Listo.")
