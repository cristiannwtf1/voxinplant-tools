
from pathlib import Path
import pandas as pd
import sys
import argparse

# === CONFIGURACIÓN GENERAL ===
INVALID_U_THRESHOLD = 5.0  # % Umbral del semáforo de calidad
MIN_FILE_SIZE_BYTES = 4096  # Ignorar archivos vacíos o incompletos
SHOW_NO_FILES_MESSAGE = True  # Mostrar mensaje si no hay archivos nuevos

BASE_DIR = Path(__file__).resolve().parent
INBOX_DIR = BASE_DIR / "inbox"
OUTPUT_DIR = BASE_DIR / "output"

COL_FECHA = "Date of call start"
COL_RESULT = "Attempt result"
COL_BTN = "btn_input"
COL_ENTIDAD = "entidad"
COL_NAME = "name"
COL_PHONE_TEMPLATE = "Phone"
COL_PHONE_DIALED = "Phone B"
COL_ATTEMPT_NUM = "Attempt number"
COL_DURATION = "Call duration"

REQUIRED_COLUMNS = [
    COL_FECHA, COL_RESULT, COL_BTN, COL_ENTIDAD, COL_NAME,
    COL_PHONE_TEMPLATE, COL_PHONE_DIALED, COL_ATTEMPT_NUM, COL_DURATION
]

def normalize_btn_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype="object")
    s_norm = (
        s.astype(str)
         .str.strip()
         .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA}, regex=False)
    )
    s_norm = s_norm.where(~s_norm.isin(["1.0", "2.0"]), s_norm.str.replace(".0", "", regex=False))
    s_norm = s_norm.where(s_norm.isin(["1", "2"]), s_norm)
    return s_norm

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df

def build_resumen_crudo(total, si, no, invalidos, sinresp, contestaron) -> pd.DataFrame:
    def pct(x): return (x / total * 100) if total else 0.0
    return pd.DataFrame({
        "Bloque": ["CRUDO"] * 6,
        "Métrica": [
            "Total registros",
            "Contestaron (Call answered)",
            "Confirmados (btn=1)",
            "No confirmados (btn=2)",
            "Inválidos (Invalid number)",
            "Sin respuesta (contestó pero no eligió)",
        ],
        "Conteo": [total, contestaron, si, no, invalidos, sinresp],
        "Porcentaje (%)": [
            100.0,
            round(pct(contestaron), 2),
            round(pct(si), 2),
            round(pct(no), 2),
            round(pct(invalidos), 2),
            round(pct(sinresp), 2),
        ],
    })

def build_resumen_unicos(scope_label, u_si, u_no, u_inv, u_sin) -> pd.DataFrame:
    u_total = u_si + u_no + u_inv + u_sin
    def pct(x): return (x / u_total * 100) if u_total else 0.0
    return pd.DataFrame({
        "Bloque": [f"ÚNICOS ({scope_label})"] * 5,
        "Métrica": [
            "Únicos Confirmados (btn=1)",
            "Únicos No confirmados (btn=2)",
            "Únicos Inválidos",
            "Únicos Sin respuesta",
            "Total únicos (suma categorías)",
        ],
        "Conteo": [u_si, u_no, u_inv, u_sin, u_total],
        "Porcentaje (%)": [
            round(pct(u_si), 2),
            round(pct(u_no), 2),
            round(pct(u_inv), 2),
            round(pct(u_sin), 2),
            100.0,
        ],
    })

def find_latest_inbox_file():
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    def is_candidate(p: Path) -> bool:
        name = p.name
        if not name.lower().endswith(".xlsx"):
            return False
        if name.startswith("~$"):  # Archivos temporales de Excel
            return False
        if "_consolidado" in p.stem.lower():
            return False
        try:
            if p.stat().st_size < MIN_FILE_SIZE_BYTES:
                return False
            with open(p, "rb"):
                pass
            return True
        except Exception:
            return False

    candidates = [p for p in INBOX_DIR.glob("*.xlsx") if is_candidate(p)]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if not candidates and SHOW_NO_FILES_MESSAGE:
        print("\n⚠️  No hay archivos nuevos en la carpeta 'inbox'.")
        print("   - Coloca aquí el reporte descargado desde Voximplant.")
        print("   - Luego ejecuta nuevamente el script.\n")
    return candidates[0] if candidates else None

def unique_keys(scope: str):
    if scope == "dialed":
        return [COL_ENTIDAD, COL_PHONE_DIALED]
    return [COL_ENTIDAD, COL_NAME, COL_PHONE_TEMPLATE]

def make_unique_by_category(df_cat: pd.DataFrame, scope: str) -> pd.DataFrame:
    keys = unique_keys(scope)
    if COL_FECHA in df_cat.columns:
        df_cat = df_cat.sort_values(by=[COL_FECHA] + keys, ascending=True, na_position="last")
    return df_cat.drop_duplicates(subset=keys, keep="last")

def main():
    parser = argparse.ArgumentParser(description="Consolida reportes Voximplant con hojas SI/NO/INVALIDOS/SIN_RESPUESTA + ÚNICOS por alcance.")
    parser.add_argument("--unique-scope", choices=["template", "dialed"], default="template",
                        help="Alcance de deduplicación para hojas UNIQUE_*: 'template' = (entidad,name,Phone) [como lo haces manualmente], 'dialed' = (entidad,Phone B).")
    args = parser.parse_args()

    if len(sys.argv) >= 2 and sys.argv[1] and not sys.argv[1].startswith("--"):
        input_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        input_path = find_latest_inbox_file()
        if not input_path:
            print(f"[ERROR] No se encontraron archivos .xlsx en {INBOX_DIR}")
            sys.exit(1)
    if not input_path.exists():
        print(f"[ERROR] El archivo no existe: {input_path}")
        sys.exit(2)

    print(f"Procesando archivo: {input_path.name} (unique-scope={args.unique_scope})")

    df = pd.read_excel(input_path)
    df = ensure_columns(df)
    df[COL_BTN] = normalize_btn_series(df[COL_BTN])
    df[COL_FECHA] = pd.to_datetime(df[COL_FECHA], errors="coerce")
    for col in [COL_PHONE_TEMPLATE, COL_PHONE_DIALED]:
        df[col] = df[col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

    total = len(df)
    contestaron = (df[COL_RESULT] == "Call answered").sum()
    df_si = df[df[COL_BTN] == "1"].copy()
    df_no = df[df[COL_BTN] == "2"].copy()
    df_invalidos = df[df[COL_RESULT] == "Invalid number"].copy()
    mask_sinresp = (df[COL_RESULT] == "Call answered") & (df[COL_BTN].isna())
    exclude = set(df_si[COL_PHONE_DIALED].dropna()) | set(df_no[COL_PHONE_DIALED].dropna())
    df_sinresp = df[mask_sinresp & (~df[COL_PHONE_DIALED].isin(exclude))].copy()

    base_cols = [
        COL_FECHA, COL_ENTIDAD, COL_NAME,
        COL_PHONE_TEMPLATE, COL_PHONE_DIALED,
        COL_RESULT, COL_BTN, COL_ATTEMPT_NUM, COL_DURATION,
    ]
    for sub in (df_si, df_no, df_invalidos, df_sinresp):
        for c in base_cols:
            if c not in sub.columns:
                sub[c] = pd.NA
        sub.sort_values(by=[COL_FECHA, COL_PHONE_DIALED], inplace=True)

    # ÚNICOS por categoría (según alcance elegido)
    u_si_df  = make_unique_by_category(df_si, args.unique_scope)
    u_no_df  = make_unique_by_category(df_no, args.unique_scope)
    u_inv_df = make_unique_by_category(df_invalidos, args.unique_scope)
    u_sin_df = make_unique_by_category(df_sinresp, args.unique_scope)

    u_si, u_no, u_inv, u_sin = len(u_si_df), len(u_no_df), len(u_inv_df), len(u_sin_df)

    # Enriquecimientos
    df_sinresp["Detalle"] = "Contestó pero no seleccionó opción"
    intentos_por_num = df.groupby(COL_PHONE_DIALED).size().rename("Intentos totales").reset_index()
    df_sinresp = df_sinresp.merge(intentos_por_num, how="left", on=COL_PHONE_DIALED)

    keys = unique_keys(args.unique_scope)
    intentos_scope = df.groupby(keys).size().rename("Intentos totales").reset_index()
    u_sin_df = u_sin_df.merge(intentos_scope, how="left", on=keys)
    u_sin_df.sort_values(by=["Intentos totales", COL_FECHA], ascending=[True, True], inplace=True)

    resumen_crudo = build_resumen_crudo(total, len(df_si), len(df_no), len(df_invalidos), len(df_sinresp), contestaron)
    scope_label = "entidad+name+Phone" if args.unique_scope=="template" else "entidad+Phone B"
    resumen_unicos = build_resumen_unicos(scope_label, u_si, u_no, u_inv, u_sin)
    resumen = pd.concat([resumen_crudo, resumen_unicos], ignore_index=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{input_path.stem}_consolidado.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="RESUMEN", index=False)
        df_si[base_cols].to_excel(writer, sheet_name="SI", index=False)
        df_no[base_cols].to_excel(writer, sheet_name="NO", index=False)
        df_invalidos[base_cols].to_excel(writer, sheet_name="INVALIDOS", index=False)
        df_sinresp[base_cols + ["Detalle", "Intentos totales"]].to_excel(writer, sheet_name="SIN_RESPUESTA", index=False)

        keep_cols = base_cols
        u_si_df[keep_cols].to_excel(writer, sheet_name="UNIQUE_SI", index=False)
        u_no_df[keep_cols].to_excel(writer, sheet_name="UNIQUE_NO", index=False)
        u_inv_df[keep_cols].to_excel(writer, sheet_name="UNIQUE_INVALIDOS", index=False)
        u_sin_df[keep_cols + ["Intentos totales"]].to_excel(writer, sheet_name="UNIQUE_SIN_RESPUESTA", index=False)
        u_sin_df[keep_cols + ["Intentos totales"]].to_excel(writer, sheet_name="REDISCAR", index=False)

    # === Copias automáticas de histórico ===
    DAILY_DIR = OUTPUT_DIR / "daily"
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    ARCHIVE_DIR = BASE_DIR / "archive_raw"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Copiar el archivo consolidado a DAILY
    daily_copy = DAILY_DIR / output_path.name
    import shutil
    shutil.copy2(output_path, daily_copy)

    # Mover el archivo original procesado a ARCHIVE_RAW
    archived_copy = ARCHIVE_DIR / input_path.name
    try:
        shutil.move(str(input_path), archived_copy)
    except Exception as e:
        print(f"[Aviso] No se pudo mover el archivo original: {e}")

    # === HISTÓRICO ÚNICO EN UN SOLO ARCHIVO ===
    import re, datetime
    from pandas import ExcelFile

    HISTORY_DIR = OUTPUT_DIR / "history"
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH = HISTORY_DIR / "HISTORICO_UNIQUE.xlsx"

    # 1) Fecha del snapshot a partir del nombre de archivo, si no, hoy
    fname = input_path.name
    m = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    snapshot_date = m.group(1) if m else datetime.date.today().isoformat()

    def add_meta(df_in: pd.DataFrame) -> pd.DataFrame:
        df_out = df_in.copy()
        df_out["snapshot_date"] = snapshot_date
        df_out["source_file"] = fname
        return df_out

    # 2) DataFrames nuevos (únicos del día) + meta
    keep_cols = base_cols
    new_SI  = add_meta(u_si_df[keep_cols])
    new_NO  = add_meta(u_no_df[keep_cols])
    new_INV = add_meta(u_inv_df[keep_cols])
    new_SIN = add_meta(u_sin_df[keep_cols + ["Intentos totales"]])

    # 3) Cargar sheets existentes si el histórico ya existe
    sheets = {
        "DATA_SI": new_SI.iloc[0:0],
        "DATA_NO": new_NO.iloc[0:0],
        "DATA_INVALIDOS": new_INV.iloc[0:0],
        "DATA_SIN_RESPUESTA": new_SIN.iloc[0:0],
    }
    if HISTORY_PATH.exists():
        try:
            with ExcelFile(HISTORY_PATH) as xf:
                for sh in sheets.keys():
                    if sh in xf.sheet_names:
                        sheets[sh] = pd.read_excel(HISTORY_PATH, sheet_name=sh)
        except Exception:
            # si falla la lectura, seguimos con hojas vacías (no debería pasar)
            pass

    # 4) Append + dedupe por clave (tu alcance template: entidad+name+Phone + snapshot/source)
    KEY_TEMPLATE = [COL_ENTIDAD, COL_NAME, COL_PHONE_TEMPLATE]

    def append_and_dedupe(df_old: pd.DataFrame, df_new: pd.DataFrame, key_cols: list) -> pd.DataFrame:
        # Alinear columnas entre viejo y nuevo
        for c in df_new.columns:
            if c not in df_old.columns:
                df_old[c] = pd.NA
        for c in df_old.columns:
            if c not in df_new.columns:
                df_new[c] = pd.NA
        combined = pd.concat([df_old, df_new], ignore_index=True)
        combined.drop_duplicates(subset=key_cols + ["snapshot_date", "source_file"], keep="last", inplace=True)
        return combined

    sheets["DATA_SI"]  = append_and_dedupe(sheets["DATA_SI"],  new_SI,  KEY_TEMPLATE)
    sheets["DATA_NO"]  = append_and_dedupe(sheets["DATA_NO"],  new_NO,  KEY_TEMPLATE)
    sheets["DATA_INVALIDOS"] = append_and_dedupe(sheets["DATA_INVALIDOS"], new_INV, KEY_TEMPLATE)
    sheets["DATA_SIN_RESPUESTA"] = append_and_dedupe(sheets["DATA_SIN_RESPUESTA"], new_SIN, KEY_TEMPLATE)

    # 5) Guardar todo en un único archivo de histórico
    with pd.ExcelWriter(HISTORY_PATH, engine="openpyxl") as w:
        for sh, df_sh in sheets.items():
            df_sh.to_excel(w, sheet_name=sh, index=False)

    # === RESUMEN_DIARIO para histórico plano (Excel + CSV) ===
    RES_DIR = OUTPUT_DIR / "history"
    RES_DIR.mkdir(parents=True, exist_ok=True)
    RES_XLSX = RES_DIR / "HIST_RESUMEN_DIARIO.xlsx"
    RES_CSV  = RES_DIR / "HIST_RESUMEN_DIARIO.csv"

    # KPIs diarios (CRUDO + ÚNICOS)
    resumen_row = pd.DataFrame([{
        "snapshot_date": snapshot_date,
        "source_file": fname,
        "total": total,
        "contestaron": int((df[COL_RESULT] == "Call answered").sum()),
        "confirmados": int(len(df_si)),
        "no_confirmados": int(len(df_no)),
        "invalidos": int(len(df_invalidos)),
        "sin_respuesta": int(len(df_sinresp)),
        "u_confirmados": int(u_si),
        "u_no_confirmados": int(u_no),
        "u_invalidos": int(u_inv),
        "u_sin_respuesta": int(u_sin),
        "u_total": int(u_si + u_no + u_inv + u_sin),
    }])

    # Calcula tasa inválidos únicos y semáforo (misma lógica que consola)
    INVALID_U_THRESHOLD = 5.0
    invalid_rate = round((u_inv / (u_si + u_no + u_inv + u_sin) * 100), 2) if (u_si + u_no + u_inv + u_sin) else 0.0
    resumen_row["invalid_rate_percent"] = invalid_rate
    resumen_row["semaforo"] = (
        "🔴 ALTO" if invalid_rate > INVALID_U_THRESHOLD
        else ("🟡 MEDIO" if invalid_rate > (INVALID_U_THRESHOLD * 0.6) else "🟢 OK")
    )

    # Función helper para append + dedupe por (snapshot_date, source_file)
    def append_dedupe_table(new_df: pd.DataFrame, path_xlsx: Path, path_csv: Path):
        # 1) Excel
        if path_xlsx.exists():
            try:
                old = pd.read_excel(path_xlsx, sheet_name="DATA")
            except Exception:
                old = pd.DataFrame(columns=new_df.columns)
        else:
            old = pd.DataFrame(columns=new_df.columns)

        # Alinear columnas
        for c in new_df.columns:
            if c not in old.columns:
                old[c] = pd.NA
        for c in old.columns:
            if c not in new_df.columns:
                new_df[c] = pd.NA

        combined = pd.concat([old, new_df], ignore_index=True)
        combined.drop_duplicates(subset=["snapshot_date", "source_file"], keep="last", inplace=True)

        with pd.ExcelWriter(path_xlsx, engine="openpyxl") as w:
            combined.to_excel(w, sheet_name="DATA", index=False)

        # 2) CSV (mismo contenido), útil para Power BI
        combined.to_csv(path_csv, index=False, encoding="utf-8-sig")

    append_dedupe_table(resumen_row, RES_XLSX, RES_CSV)

    print("\n=== CONSOLIDACIÓN LISTA ===")
    print(f"Entrada: {input_path}")
    print(f"Salida:  {output_path}\n")

    # --- Consola: CRUDO ---
    print("== RESUMEN CRUDO ==")
    print(f"Total registros:                    {total}")
    print(f"Contestaron (Call answered):        {(df[COL_RESULT] == 'Call answered').sum()}")
    print(f"Confirmados (btn=1):               {len(df_si)}")
    print(f"No confirmados (btn=2):            {len(df_no)}")
    print(f"Inválidos (Invalid number):        {len(df_invalidos)}")
    print(f"Sin respuesta (contestó sin btn):  {len(df_sinresp)}")

    # --- ÚNICOS por tu método (entidad+name+Phone por defecto) ---
    u_total = u_si + u_no + u_inv + u_sin
    print("\n== RESUMEN ÚNICOS (entidad+name+Phone) ==")
    print(f"Únicos Confirmados (btn=1):        {u_si}")
    print(f"Únicos No confirmados (btn=2):     {u_no}")
    print(f"Únicos Inválidos:                  {u_inv}")
    print(f"Únicos Sin respuesta:              {u_sin}")
    print(f"Total únicos (suma categorías):    {u_total}")

    # --- Semáforo de calidad (Inválidos únicos) ---
    INVALID_U_THRESHOLD = 5.0  # % umbral
    invalid_rate = round((u_inv / u_total) * 100, 2) if u_total else 0.0
    semaforo = "🟢 OK"
    if invalid_rate > INVALID_U_THRESHOLD:
        semaforo = "🔴 ALTO"
    elif invalid_rate > (INVALID_U_THRESHOLD * 0.6):
        semaforo = "🟡 MEDIO"

    print("\n== SEMÁFORO CALIDAD TELÉFONOS ==")
    print(f"Inválidos únicos: {u_inv} de {u_total}  ({invalid_rate}%)  → {semaforo}")
    print(f"(Umbral: {INVALID_U_THRESHOLD}%)")

    # También dejamos el DataFrame completo por si lo quieres en Excel con dos bloques:
    # print(resumen.to_string(index=False))

if __name__ == "__main__":
    main()
