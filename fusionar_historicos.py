import pandas as pd
from pathlib import Path
from pandas import ExcelFile
import re
from datetime import datetime

# =========================
# Rutas base / archivos
# =========================
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output" / "history"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1) Base manual (la que llevabas en escritorio)
MANUAL_PATH = OUT_DIR / "MANUAL_SNAPSHOT.xlsx"

# Control de uso de manual
USE_MANUAL = True

# 2) Histórico automático que genera el consolidador
AUTO_PATH = OUT_DIR / "HISTORICO_UNIQUE.xlsx"

# 3) Salidas unificadas (para BI y para tu “conteo por hojas”)
OUT_XLSX = OUT_DIR / "BASE_HISTORICA_UNIFICADA.xlsx"
OUT_CSV  = OUT_DIR / "BASE_HISTORICA_UNIFICADA.csv"

# 4) Log opcional de auditoría
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "fusionar_historicos.log"


# =========================
# Utilidades
# =========================
def norm_name(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()

def norm_phone(s: pd.Series) -> pd.Series:
    # quita .0 y espacios; conserva + y dígitos
    s = s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    s = s.str.replace(r"[^\d+]", "", regex=True)
    return s

def to_date_only(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s, errors="coerce")
    return d.dt.date.astype("string")

def take_first_nonnull(row, cols):
    for c in cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip() != "":
            return row[c]
    return pd.NA

def safe_fillna_str(df: pd.DataFrame) -> pd.DataFrame:
    """Evita FutureWarning al llenar NaN con '', convirtiendo a object primero."""
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]) or pd.api.types.is_integer_dtype(df[c]):
            # no tocar campos numéricos
            continue
        df[c] = df[c].astype("object")
    return df.where(pd.notna(df), "")


# =========================
# Carga Manual
# =========================
def load_manual(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[ERROR] No se encuentra el manual: {path}")
        return pd.DataFrame()

    mapping = {
        "Localizados": "SI",
        "RespondenNO": "NO",
        "TelefonosInvalidos": "INVALIDO",
        "Contesta_NoResponde": "NO RESPONDE",
    }

    frames = []
    with ExcelFile(path) as xf:
        sheet_names = xf.sheet_names

    for sh, cat in mapping.items():
        if sh not in sheet_names:
            print(f"[Aviso] Hoja manual no encontrada: {sh}")
            continue

        df = pd.read_excel(path, sheet_name=sh)

        # Normaliza encabezados por espacios extra
        df = df.rename(columns={c: c.strip() for c in df.columns})

        # Campos esperados (si falta alguno, se crea vacío)
        tipo_id = df.get("Tipo Identificación", pd.NA)
        num_id  = df.get("Nº Identificación", pd.NA)
        nombre  = df.get("Nombre", pd.NA)
        email   = df.get("Email", pd.NA)
        tel1    = df.get("Telefono1", pd.NA)
        tel2    = df.get("Telefono2", pd.NA)
        tel3    = df.get("Telefono3", pd.NA)
        fecha   = df.get("Fecha", pd.NA)
        conf    = df.get("Confirma Identidad", pd.NA)
        tel_inv = df.get("TELEFONO1 INVALIDO", pd.NA)

        out = pd.DataFrame({
            "tipo_id": tipo_id,
            "num_id": num_id,
            "name": nombre,
            "email": email,
            "telefono1": tel1,
            "telefono2": tel2,
            "telefono3": tel3,
            "telefono_invalido": tel_inv,
            "confirma_identidad": conf,
            "fecha_llamada": fecha,
        })

        # Derivados
        out["source"] = "manual"
        out["categoria"] = cat

        # Teléfono principal
        out["telefono"] = out.apply(
            lambda r: r["telefono_invalido"] if cat == "INVALIDO" else take_first_nonnull(r, ["telefono1"]),
            axis=1
        )

        # Normalizaciones
        for col in ["name", "email"]:
            if col in out.columns:
                out[col] = norm_name(out[col])
        for col in ["telefono", "telefono1", "telefono2", "telefono3", "telefono_invalido"]:
            if col in out.columns:
                out[col] = norm_phone(out[col])
        out["fecha_llamada"] = to_date_only(out["fecha_llamada"])
        out["snapshot_date"] = out["fecha_llamada"]  # en manual, usamos la misma
        out["source_file"] = path.name
        out["entidad"] = pd.NA  # manual no trae entidad

        # En inválidos, si no viene “confirma”, marcamos como INVALIDO
        if cat == "INVALIDO":
            out["confirma_identidad"] = out["confirma_identidad"].fillna("INVALIDO")

        frames.append(out)

    if not frames:
        return pd.DataFrame()

    manual = pd.concat(frames, ignore_index=True)
    manual = manual.dropna(subset=["name", "telefono"], how="any")

    manual = manual[[
        "snapshot_date", "source_file", "source", "categoria", "confirma_identidad",
        "tipo_id", "num_id", "name", "email",
        "telefono", "telefono1", "telefono2", "telefono3", "telefono_invalido",
        "entidad", "fecha_llamada"
    ]]

    return manual


# =========================
# Carga Automática (HISTORICO_UNIQUE.xlsx)
# =========================
def load_auto(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[Aviso] No existe {path}. Solo se fusionará manual.")
        return pd.DataFrame()

    sheets = {
        "DATA_SI": "SI",
        "DATA_NO": "NO",
        "DATA_INVALIDOS": "INVALIDO",
        "DATA_SIN_RESPUESTA": "NO RESPONDE",
    }

    frames = []
    with ExcelFile(path) as xf:
        shs = xf.sheet_names

    for sh, cat in sheets.items():
        if sh not in shs:
            print(f"[Aviso] Hoja automática no encontrada: {sh}")
            continue

        df = pd.read_excel(path, sheet_name=sh)

        # === Bloque actualizado ===
        out = pd.DataFrame({
            "snapshot_date": df.get("snapshot_date", pd.NA),
            "source_file": df.get("source_file", pd.NA),
            "source": "automático",
            "categoria": cat,
            "confirma_identidad": df.get("btn_input", pd.NA).astype("string"),
            "tipo_id": pd.NA,
            "num_id": pd.NA,
            "name": df.get("name", pd.NA),
            "email": pd.NA,
            # Teléfono principal
            "telefono": df.get("Phone", pd.NA),
            # 👉 Campos nuevos para mantener coherencia con el manual
            "telefono1": df.get("Phone", pd.NA) if cat in ("SI", "NO", "NO RESPONDE") else pd.NA,
            "telefono2": pd.NA,
            "telefono3": pd.NA,
            "telefono_invalido": df.get("Phone", pd.NA) if cat == "INVALIDO" else pd.NA,
            "entidad": df.get("entidad", pd.NA),
            "fecha_llamada": df.get("Date of call start", pd.NA),
        })
        # ===========================

        # Normalizaciones
        out["name"] = norm_name(out["name"].fillna(""))
        out["telefono"] = norm_phone(out["telefono"])
        out["fecha_llamada"] = to_date_only(out["fecha_llamada"])

        # Mapear btn_input {1 -> SI, 2 -> NO}
        ci = out["confirma_identidad"].str.strip()
        out.loc[ci == "1", "confirma_identidad"] = "SI"
        out.loc[ci == "2", "confirma_identidad"] = "NO"
        out.loc[out["categoria"] == "NO RESPONDE", "confirma_identidad"] = "NO RESPONDE"
        out.loc[out["categoria"] == "INVALIDO", "confirma_identidad"] = "INVALIDO"

        frames.append(out)

    if not frames:
        return pd.DataFrame()

    auto = pd.concat(frames, ignore_index=True)
    auto = auto.dropna(subset=["name", "telefono"], how="any")

    auto = auto[[
        "snapshot_date", "source_file", "source", "categoria", "confirma_identidad",
        "tipo_id", "num_id", "name", "email",
        "telefono", "telefono1", "telefono2", "telefono3", "telefono_invalido",
        "entidad", "fecha_llamada"
    ]]

    return auto


# =========================
# Main
# =========================
def main():
    print("Cargando manual ...")
    if USE_MANUAL:
        dfm = load_manual(MANUAL_PATH)
        print(f"  → {len(dfm)} filas manuales")
    else:
        dfm = pd.DataFrame()
        print("  → (Omitido: lectura de manual desactivada)")

    print("Cargando automático ...")
    dfa = load_auto(AUTO_PATH)
    print(f"  → {len(dfa)} filas automáticas")

    # Unión + limpieza básica
    df = pd.concat([dfm, dfa], ignore_index=True)
    df = df[df["telefono"].notna() & (df["telefono"].astype(str).str.len() > 0)]

    # Dedupe por día + fuente + categoría + name + telefono
    df.drop_duplicates(
        subset=["snapshot_date", "source", "categoria", "name", "telefono"],
        keep="last",
        inplace=True
    )

    # Orden agradable
    df.sort_values(by=["snapshot_date", "categoria", "entidad", "name"], inplace=True, na_position="last")

    # RESUMEN (conteos por día/categoría)
    resumen = (
        df.groupby(["snapshot_date", "categoria"], dropna=False)
          .size()
          .reset_index(name="conteo")
          .sort_values(["snapshot_date", "categoria"])
    )

    # Normalizar confirmación en mayúsculas
    df["confirma_identidad"] = df["confirma_identidad"].astype("string").str.upper()

    # === VISTAS estilo manual (históricas) ===
    si_view = (
        df[df["categoria"] == "SI"]
        .loc[:, ["tipo_id","num_id","name","email","telefono1","telefono2","telefono3","confirma_identidad","fecha_llamada","snapshot_date","source"]]
        .rename(columns={
            "tipo_id": "Tipo Identificación",
            "num_id": "Nº Identificación",
            "name": "Nombre",
            "email": "Email",
            "telefono1": "Telefono1",
            "telefono2": "Telefono2",
            "telefono3": "Telefono3",
            "confirma_identidad": "Confirma Identidad",
            "fecha_llamada": "Fecha"
        })
        .sort_values(by=["snapshot_date","Nombre"], na_position="last")
    )

    no_view = (
        df[df["categoria"] == "NO"]
        .loc[:, ["tipo_id","num_id","name","email","telefono1","telefono2","telefono3","confirma_identidad","fecha_llamada","snapshot_date","source"]]
        .rename(columns={
            "tipo_id": "Tipo Identificación",
            "num_id": "Nº Identificación",
            "name": "Nombre",
            "email": "Email",
            "telefono1": "Telefono1",
            "telefono2": "Telefono2",
            "telefono3": "Telefono3",
            "confirma_identidad": "Confirma Identidad",
            "fecha_llamada": "Fecha"
        })
        .sort_values(by=["snapshot_date","Nombre"], na_position="last")
    )

    invalidos_view = (
        df[df["categoria"] == "INVALIDO"]
        .loc[:, ["num_id","name","telefono"]]
        .rename(columns={
            "num_id": "Nº Identificación",
            "name": "Nombre",
            "telefono": "TELEFONO1 INVALIDO"
        })
        .sort_values(by=["Nombre"], na_position="last")
    )

    noresp_view = (
        df[df["categoria"] == "NO RESPONDE"]
        .loc[:, ["tipo_id","num_id","name","email","telefono1","telefono2","telefono3","confirma_identidad","fecha_llamada","snapshot_date","source"]]
        .rename(columns={
            "tipo_id": "Tipo Identificación",
            "num_id": "Nº Identificación",
            "name": "Nombre",
            "email": "Email",
            "telefono1": "Telefono1",
            "telefono2": "Telefono2",
            "telefono3": "Telefono3",
            "confirma_identidad": "Confirma Identidad",
            "fecha_llamada": "Fecha"
        })
        .sort_values(by=["snapshot_date","Nombre"], na_position="last")
    )

    # Evitar NaN visibles en Excel (sin FutureWarnings)
    si_view       = safe_fillna_str(si_view)
    no_view       = safe_fillna_str(no_view)
    invalidos_view= safe_fillna_str(invalidos_view)
    noresp_view   = safe_fillna_str(noresp_view)
    resumen       = safe_fillna_str(resumen)

    # ================
    # Confirmación final
    # ================
    # 1) Lee el conteo anterior ANTES de escribir (si existe)
    prev_count = 0
    if OUT_XLSX.exists():
        try:
            prev_data = pd.read_excel(OUT_XLSX, sheet_name="DATA", usecols=["snapshot_date"])
            prev_count = len(prev_data)
        except Exception:
            prev_count = 0

    # 2) Escribe Excel (hojas en orden) + CSV plano BI
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
        resumen.to_excel(w, sheet_name="RESUMEN", index=False)
        si_view.to_excel(w, sheet_name="Localizados", index=False)
        no_view.to_excel(w, sheet_name="RespondenNO", index=False)
        invalidos_view.to_excel(w, sheet_name="TelefonosInvalidos", index=False)
        noresp_view.to_excel(w, sheet_name="Contesta_NoResponde", index=False)
        df.to_excel(w, sheet_name="DATA", index=False)

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    # 3) Cálculo de nuevos
    new_count = len(df)
    added_rows = new_count - prev_count if prev_count > 0 else new_count

    # 4) Última fecha robusta
    last_date = pd.to_datetime(df["snapshot_date"], errors="coerce").max()
    last_date_str = "" if pd.isna(last_date) else str(last_date.date())

    # 5) Mensaje final
    print("\n✅ Histórico unificado generado:")
    print(f"  - {OUT_XLSX}")
    print(f"  - {OUT_CSV}")
    print(f"📈 Registros nuevos añadidos: {added_rows}")
    print(f"📊 Total acumulado en histórico: {new_count} filas")
    print("📘 Hojas: RESUMEN, Localizados, RespondenNO, TelefonosInvalidos, Contesta_NoResponde, DATA")
    print(f"🕒 Última fecha detectada en snapshot_date: {last_date_str}")

    # 6) Log (opcional, pero recomendado)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{now} | added={added_rows} | total={new_count} | last_date={last_date_str}\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
