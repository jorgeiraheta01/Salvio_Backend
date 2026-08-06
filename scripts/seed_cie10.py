"""Siembra el catalogo CIE-10 (cie10_catalog) en todas las bases de tenant.

Deliberadamente un set REDUCIDO (~100 codigos) de diagnosticos comunes en
medicina general, elegidos por alta confianza en su exactitud -- no es el
CIE-10 completo (serian miles de codigos) ni un intento de cubrir
especialidades poco comunes. Se amplia con el tiempo desde el mismo CRUD
(POST /api/v1/catalogs/cie10) a medida que cada clinica lo necesite, en vez
de importar de una sola vez un dataset no verificado.

Idempotente: usa INSERT IGNORE sobre code (UNIQUE), correr multiples veces
no duplica filas.

Uso: .venv/Scripts/python.exe scripts/seed_cie10.py [--only salvio_clinica_x]
"""

import argparse
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]

DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASSWORD = "rootroot"

RESERVED_DB_NAMES = {"salvio_control"}

# (codigo, descripcion, categoria)
CIE10_CODES: list[tuple[str, str, str]] = [
    # Infecciosas / parasitarias
    ("A09", "Diarrea y gastroenteritis de presunto origen infeccioso", "Infecciosas"),
    ("A90", "Dengue", "Infecciosas"),
    ("B01.9", "Varicela sin complicaciones", "Infecciosas"),
    ("B34.9", "Infeccion viral no especificada", "Infecciosas"),
    ("J00", "Rinofaringitis aguda (resfriado comun)", "Respiratorio"),
    ("J02.9", "Faringitis aguda no especificada", "Respiratorio"),
    ("J03.9", "Amigdalitis aguda no especificada", "Respiratorio"),
    ("J06.9", "Infeccion aguda de vias respiratorias superiores no especificada", "Respiratorio"),
    # Endocrinas / metabolicas
    ("E10.9", "Diabetes mellitus tipo 1 sin complicaciones", "Endocrino"),
    ("E11.9", "Diabetes mellitus tipo 2 sin complicaciones", "Endocrino"),
    ("E03.9", "Hipotiroidismo no especificado", "Endocrino"),
    ("E05.9", "Tirotoxicosis no especificada", "Endocrino"),
    ("E66.9", "Obesidad no especificada", "Endocrino"),
    ("E78.5", "Hiperlipidemia no especificada", "Endocrino"),
    ("E86.0", "Deplecion de volumen (deshidratacion)", "Endocrino"),
    # Mentales / conductuales
    ("F32.9", "Episodio depresivo no especificado", "Salud mental"),
    ("F41.1", "Trastorno de ansiedad generalizada", "Salud mental"),
    ("F41.9", "Trastorno de ansiedad no especificado", "Salud mental"),
    ("F51.0", "Insomnio no organico", "Salud mental"),
    # Sistema nervioso
    ("G43.0", "Migrana sin aura", "Neurologia"),
    ("G43.1", "Migrana con aura", "Neurologia"),
    ("G43.9", "Migrana no especificada", "Neurologia"),
    ("G47.0", "Trastornos del inicio y mantenimiento del sueno", "Neurologia"),
    # Ojo
    ("H10.9", "Conjuntivitis no especificada", "Oftalmologia"),
    ("H52.1", "Miopia", "Oftalmologia"),
    ("H52.4", "Presbicia", "Oftalmologia"),
    # Oido
    ("H61.2", "Cerumen impactado", "Otorrinolaringologia"),
    ("H66.9", "Otitis media no especificada", "Otorrinolaringologia"),
    ("H81.1", "Vertigo paroxistico benigno", "Otorrinolaringologia"),
    # Circulatorias
    ("I10", "Hipertension esencial (primaria)", "Cardiologia"),
    ("I20.9", "Angina de pecho no especificada", "Cardiologia"),
    ("I25.9", "Enfermedad isquemica cronica del corazon no especificada", "Cardiologia"),
    ("I48.9", "Fibrilacion y aleteo auricular no especificado", "Cardiologia"),
    ("I50.9", "Insuficiencia cardiaca no especificada", "Cardiologia"),
    ("I83.9", "Varices de miembros inferiores sin ulcera ni inflamacion", "Cardiologia"),
    ("I84.9", "Hemorroides no especificadas", "Cardiologia"),
    # Respiratorias
    ("J01.9", "Sinusitis aguda no especificada", "Respiratorio"),
    ("J18.9", "Neumonia no especificada", "Respiratorio"),
    ("J20.9", "Bronquitis aguda no especificada", "Respiratorio"),
    ("J30.4", "Rinitis alergica no especificada", "Respiratorio"),
    ("J44.9", "Enfermedad pulmonar obstructiva cronica no especificada", "Respiratorio"),
    ("J45.9", "Asma no especificada", "Respiratorio"),
    # Digestivas
    ("K02.9", "Caries dental no especificada", "Digestivo"),
    ("K21.0", "Enfermedad por reflujo gastroesofagico con esofagitis", "Digestivo"),
    ("K21.9", "Enfermedad por reflujo gastroesofagico sin esofagitis", "Digestivo"),
    ("K29.7", "Gastritis no especificada", "Digestivo"),
    ("K30", "Dispepsia funcional", "Digestivo"),
    ("K52.9", "Gastroenteritis y colitis no infecciosa no especificada", "Digestivo"),
    ("K58.9", "Sindrome del intestino irritable sin diarrea", "Digestivo"),
    ("K59.0", "Estrenimiento", "Digestivo"),
    ("K80.2", "Calculo de la vesicula biliar sin colecistitis", "Digestivo"),
    # Piel
    ("L01.0", "Impetigo no especificado", "Dermatologia"),
    ("L02.9", "Absceso cutaneo no especificado", "Dermatologia"),
    ("L20.9", "Dermatitis atopica no especificada", "Dermatologia"),
    ("L23.9", "Dermatitis alergica de contacto no especificada", "Dermatologia"),
    ("L30.9", "Dermatitis no especificada", "Dermatologia"),
    ("L50.9", "Urticaria no especificada", "Dermatologia"),
    # Musculoesqueleticas
    ("M25.50", "Dolor articular no especificado", "Traumatologia"),
    ("M43.6", "Torticolis", "Traumatologia"),
    ("M54.2", "Cervicalgia", "Traumatologia"),
    ("M54.5", "Dolor lumbar bajo (lumbago)", "Traumatologia"),
    ("M54.9", "Dorsalgia no especificada", "Traumatologia"),
    ("M79.1", "Mialgia", "Traumatologia"),
    ("M79.7", "Fibromialgia", "Traumatologia"),
    # Genitourinarias
    ("N30.90", "Cistitis no especificada", "Urologia"),
    ("N39.0", "Infeccion de vias urinarias sitio no especificado", "Urologia"),
    ("N40", "Hiperplasia de la prostata", "Urologia"),
    ("N92.6", "Menstruacion irregular", "Ginecologia"),
    # Embarazo / perinatal
    ("Z34.9", "Supervision de embarazo normal no especificado", "Ginecologia"),
    ("P59.9", "Ictericia neonatal no especificada", "Pediatria"),
    # Sintomas y signos
    ("R05", "Tos", "Sintomas"),
    ("R06.0", "Disnea", "Sintomas"),
    ("R10.4", "Dolor abdominal no especificado", "Sintomas"),
    ("R11.0", "Nausea", "Sintomas"),
    ("R11.10", "Vomito no especificado", "Sintomas"),
    ("R42", "Mareo y desvanecimiento", "Sintomas"),
    ("R50.9", "Fiebre no especificada", "Sintomas"),
    ("R51", "Cefalea", "Sintomas"),
    ("R55", "Sincope y colapso", "Sintomas"),
    # Traumatismos
    ("S01.9", "Herida abierta de la cabeza, parte no especificada", "Trauma"),
    ("S06.0", "Conmocion cerebral", "Trauma"),
    ("S52.9", "Fractura del antebrazo, parte no especificada", "Trauma"),
    ("S93.4", "Esguince y torcedura del tobillo", "Trauma"),
    # Factores que influyen en el estado de salud (control/prevencion)
    ("Z00.0", "Examen medico general", "Control"),
    ("Z23", "Necesidad de inmunizacion contra enfermedad bacteriana unica", "Control"),
    ("Z71.3", "Consulta dietetica", "Control"),
    ("Z76.0", "Repeticion de prescripcion", "Control"),
]


def connect(database: str | None = None):
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=database, autocommit=False)


def target_databases(only: str | None) -> list[str]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW DATABASES LIKE 'salvio\\_%'")
            names = [row[0] for row in cur.fetchall() if row[0] not in RESERVED_DB_NAMES]
    finally:
        conn.close()
    if only:
        if only not in names:
            raise SystemExit(f"'{only}' no es una base de datos salvio_* conocida.")
        return [only]
    return names


def seed_database(db_name: str) -> int:
    conn = connect(db_name)
    inserted = 0
    try:
        with conn.cursor() as cur:
            for code, description, category in CIE10_CODES:
                cur.execute(
                    "INSERT IGNORE INTO cie10_catalog (id, code, description, category, is_active) VALUES (UUID_TO_BIN(UUID()), %s, %s, %s, 1)",
                    (code, description, category),
                )
                inserted += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="limitar a una sola base de datos")
    args = parser.parse_args()

    dbs = target_databases(args.only)
    print(f"Sembrando {len(CIE10_CODES)} codigos CIE-10 en {len(dbs)} BD(s)...")
    for db_name in dbs:
        count = seed_database(db_name)
        print(f"  [OK] {db_name}: {count} codigos nuevos insertados")
    print("Listo.")
