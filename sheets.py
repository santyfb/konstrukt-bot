"""
KONSTRUKT — Capa de base de datos con Google Sheets
Maneja todas las operaciones de lectura/escritura
"""

import json
import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_OBRAS     = "Obras"
SHEET_ETAPAS    = "Etapas"
SHEET_PERSONAL  = "Personal"
SHEET_TAREAS    = "Tareas"
SHEET_NOTAS     = "Notas"


class SheetsDB:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id

        google_creds_json = os.getenv("GCP_CREDENTIALS")
        print("GCP_CREDENTIALS presente:", bool(google_creds_json))
        if google_creds_json:
            info = json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds)
        self.sheet = service.spreadsheets()

    # ─────────────────────────────────────────
    # LECTURA GENÉRICA
    # ─────────────────────────────────────────
    def _read(self, range_name: str):
        result = self.sheet.values().get(
            spreadsheetId=self.spreadsheet_id,
            range=range_name
        ).execute()
        return result.get("values", [])

    def _append(self, range_name: str, values: list):
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [values]}
        ).execute()

    def _update_cell(self, range_name: str, value):
        self.sheet.values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [[value]]}
        ).execute()

    def _get_all_rows(self, sheet_name: str):
        rows = self._read(f"{sheet_name}!A:Z")
        if not rows or len(rows) < 2:
            return []
        headers = rows[0]
        return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in rows[1:]]

    # ─────────────────────────────────────────
    # OBRAS
    # ─────────────────────────────────────────
    def get_obras(self):
        """Retorna lista de obras activas"""
        rows = self._get_all_rows(SHEET_OBRAS)
        return [r for r in rows if r.get("status", "") != "archivada"]

    def add_obra(self, nombre: str, cliente: str, inicio: str, entrega: str) -> str:
        # El ID es el nombre que escribe el usuario (ej: "45-02")
        obra_id = nombre.strip()
        self._append(SHEET_OBRAS, [obra_id, nombre, "activa", inicio, entrega, cliente])
        return obra_id

    def get_obra_detalle(self, obra_id: str):
        """Retorna una obra con sus etapas"""
        obras = self._get_all_rows(SHEET_OBRAS)
        obra = next((o for o in obras if o["id"] == obra_id), None)
        if not obra:
            return None
        obra["etapas"] = self.get_etapas(obra_id)
        return obra

    # ─────────────────────────────────────────
    # ETAPAS
    # ─────────────────────────────────────────
    def get_etapas(self, obra_id: str):
        rows = self._get_all_rows(SHEET_ETAPAS)
        etapas = [r for r in rows if r.get("obra_id") == obra_id]
        for e in etapas:
            e["pct"] = int(e.get("pct", 0))
        return sorted(etapas, key=lambda x: int(x.get("orden", 0)))

    def update_etapa_pct(self, obra_id: str, etapa_nombre: str, pct: int):
        rows = self._read(f"{SHEET_ETAPAS}!A:F")
        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 2 and row[0] == obra_id and row[1] == etapa_nombre:
                self._update_cell(f"{SHEET_ETAPAS}!D{i}", pct)
                status = "completa" if pct == 100 else "en-curso" if pct > 0 else "pendiente"
                self._update_cell(f"{SHEET_ETAPAS}!E{i}", status)
                break

    # ─────────────────────────────────────────
    # PERSONAL
    # ─────────────────────────────────────────
    def get_personal_por_obra(self, obra_id: str):
        rows = self._get_all_rows(SHEET_PERSONAL)
        return [r for r in rows if r.get("obra_id") == obra_id]

    def get_all_personal(self):
        return self._get_all_rows(SHEET_PERSONAL)

    # ─────────────────────────────────────────
    # TAREAS
    # ─────────────────────────────────────────
    def get_tareas_activas(self):
        rows = self._get_all_rows(SHEET_TAREAS)
        return [r for r in rows if r.get("status") not in ("completa", "archivada")]

    def get_tareas_por_obra(self, obra_id: str):
        rows = self._get_all_rows(SHEET_TAREAS)
        return [r for r in rows if r.get("obra_id") == obra_id]

    def add_tarea(self, desc, obra_id, persona, fecha, creado_por, creado_en):
        tareas = self._get_all_rows(SHEET_TAREAS)
        num = len(tareas) + 1
        tarea_id = f"T-{str(num).zfill(3)}"
        self._append(SHEET_TAREAS, [
            tarea_id, desc, obra_id, persona, fecha, "pendiente", creado_por, creado_en, ""
        ])
        return tarea_id

    def update_tarea_status(self, tarea_id: str, status: str, nota: str = ""):
        rows = self._read(f"{SHEET_TAREAS}!A:I")
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0] == tarea_id:
                self._update_cell(f"{SHEET_TAREAS}!F{i}", status)
                if nota:
                    self._update_cell(f"{SHEET_TAREAS}!I{i}", nota)
                break

    # ─────────────────────────────────────────
    # NOTAS
    # ─────────────────────────────────────────
    def add_nota(self, autor: str, fecha: str, texto: str, obra_id: str):
        notas = self._get_all_rows(SHEET_NOTAS)
        num = len(notas) + 1
        nota_id = f"N-{str(num).zfill(3)}"
        self._append(SHEET_NOTAS, [nota_id, autor, fecha, texto, obra_id])
        return nota_id

    def get_notas_por_obra(self, obra_id: str):
        rows = self._get_all_rows(SHEET_NOTAS)
        return [r for r in rows if r.get("obra_id") == obra_id]

    def add_personal(self, nombre: str, rol: str, obra_id: str, obra_nombre: str):
        personal = self._get_all_rows(SHEET_PERSONAL)
        num = len(personal) + 1
        pers_id = f"P{str(num).zfill(3)}"
        self._append(SHEET_PERSONAL, [pers_id, nombre, rol, obra_id, obra_nombre])
        return pers_id
