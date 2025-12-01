import pandas as pd
from pathlib import Path
from pandas import ExcelFile

BASE = Path(__file__).resolve().parent
HIST = BASE / "output" / "history" / "HISTORICO_UNIQUE.xlsx"

# 🎯 Lista base de entidades (ajústala a tu realidad; agrega más si aplica)
ENTIDADES = {
    "BANCO CAJA SOCIAL","BANCO DE BOGOTA","BANCOLOMBIA","DAVIVIENDA","FNG",
    "COLPATRIA","FALABELLA","BANCO AGRARIO","BBVA","AV VILLAS","ITAU","BANCO POPULAR"
}

def is_like_entidad(x: str) -> bool:
    if not isinstance(x, str): return False
    s = x.strip().upper()
    if len(s) < 4: return False
    # heurística: si el “nombre” coincide 100% con una palabra típica de entidad
    return s in ENTIDADES

def audit_sheet(df: pd.DataFrame, sheet_name: str):
    if df.empty: 
        return []
    # normaliza
    for c in ("entidad","name","snapshot_date","source_file"):
        if c not in df.columns: df[c] = pd.NA
        df[c] = df[c].astype("string")
    df["name_UP"] = df["name"].str.upper()

    # % de filas por día con name que “parece” entidad
    res = (
        df.assign(flag=df["name"].apply(is_like_entidad))
          .groupby(["snapshot_date","source_file"], dropna=False)["flag"]
          .mean()
          .reset_index()
          .rename(columns={"flag":"pct_name_parece_entidad"})
          .sort_values(["snapshot_date","source_file"])
    )
    res["sheet"] = sheet_name
    return res.to_dict("records")

def main():
    if not HIST.exists():
        print(f"[ERROR] No existe {HIST}")
        return
    out_rows = []
    with ExcelFile(HIST) as xf:
        for sh in ("DATA_SI","DATA_NO","DATA_INVALIDOS","DATA_SIN_RESPUESTA"):
            if sh not in xf.sheet_names: 
                continue
            df = pd.read_excel(HIST, sheet_name=sh)
            out_rows += audit_sheet(df, sh)
    out = pd.DataFrame(out_rows)
    if out.empty:
        print("Sin datos para auditar.")
        return
    # Resumen por día (tomando el máximo entre hojas para ser conservadores)
    dia = (out.groupby(["snapshot_date","source_file"], dropna=False)["pct_name_parece_entidad"]
              .max()
              .reset_index()
              .sort_values("snapshot_date"))
    print("\n=== SOSPECHAS DE DÍA CRUZADO (name≈entidad) ===")
    if not dia.empty:
        print(dia.to_string(index=False))
    # Señala días por encima de 0.5 (50%) como probables errores
    sospechosos = dia[dia["pct_name_parece_entidad"] >= 0.5]
    if not sospechosos.empty:
        print("\n⚠️ Días sospechosos (>=50%):")
        print(sospechosos.to_string(index=False))
    else:
        print("\n✅ No se detectaron días con indicios fuertes de cruce de columnas.")

if __name__ == "__main__":
    main()
