import pandas as pd
from pathlib import Path

# === RUTAS ===
BASE_DIR = Path(__file__).resolve().parent
HIST_PATH = BASE_DIR / "output" / "history" / "HISTORICO_UNIQUE.xlsx"

# === QUÉ DÍA/ARCHIVO CORREGIR ===
# Ajusta solo si tu archivo se llama diferente. Usa exactamente lo que ves en la columna 'source_file' de HISTORICO_UNIQUE.
OBJETIVOS = [
    {"snapshot_date": "2025-11-11", "source_file": "Report_2025-11-11.xlsx"},
]

# Hojas esperadas del histórico único
SHEETS = ["DATA_SI", "DATA_NO", "DATA_INVALIDOS", "DATA_SIN_RESPUESTA"]

def carga_o_vacio(path, sheet):
    try:
        return pd.read_excel(path, sheet_name=sheet)
    except Exception:
        return pd.DataFrame()

def aplica_swap(df, objetivo):
    if df.empty:
        return df, 0

    # Aseguramos columnas mínimas
    for c in ["snapshot_date", "source_file", "entidad", "name"]:
        if c not in df.columns:
            df[c] = pd.NA

    mask = (
        (df["snapshot_date"].astype(str) == objetivo["snapshot_date"]) &
        (df["source_file"].astype(str)  == objetivo["source_file"])
    )
    idx = df.index[mask]
    if len(idx) == 0:
        return df, 0

    # Intercambiar valores entre columnas 'entidad' y 'name' SOLO en esas filas
    entidad_old = df.loc[idx, "entidad"].copy()
    name_old    = df.loc[idx, "name"].copy()

    df.loc[idx, "entidad"] = name_old
    df.loc[idx, "name"]    = entidad_old

    return df, len(idx)

def main():
    if not HIST_PATH.exists():
        print(f"[ERROR] No existe {HIST_PATH}")
        return

    # Cargar todas las hojas en memoria
    data = {sh: carga_o_vacio(HIST_PATH, sh) for sh in SHEETS}

    # Aplicar correcciones objetivo por objetivo
    totales_mod = {sh: 0 for sh in SHEETS}
    for obj in OBJETIVOS:
        for sh in SHEETS:
            df = data.get(sh, pd.DataFrame())
            df_corr, n = aplica_swap(df, obj)
            data[sh] = df_corr
            totales_mod[sh] += n

    # Guardar de vuelta (sobrescribe)
    with pd.ExcelWriter(HIST_PATH, engine="openpyxl") as w:
        for sh, df in data.items():
            # Conserva estructura original de columnas
            df.to_excel(w, sheet_name=sh, index=False)

    # Reporte
    print("✅ Corrección aplicada en HISTORICO_UNIQUE.xlsx")
    for sh in SHEETS:
        print(f"   - {sh}: filas modificadas = {totales_mod[sh]}")

if __name__ == "__main__":
    main()
