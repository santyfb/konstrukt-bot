"""
KONSTRUKT BOT — Bot de Telegram para gestión de astillero
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)
from sheets import SheetsDB

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

db = SheetsDB(SPREADSHEET_ID)

(
    NOTA_TEXTO, NOTA_OBRA_NUEVA_NOMBRE,
    TAREA_DESC, TAREA_OBRA, TAREA_OBRA_NUEVA_NOMBRE, TAREA_PERSONA, TAREA_FECHA,
    OBRA_NOMBRE, OBRA_CLIENTE, OBRA_ENTREGA,
    TAREA_INCOMPLETA_MOTIVO,
) = range(11)


# ══════════════════════════════════════════════════════════
# HELPER — teclado de obras con opción "Nueva obra"
# ══════════════════════════════════════════════════════════
def keyboard_obras(prefix: str):
    """Genera teclado con obras existentes + botón Nueva Obra"""
    obras = db.get_obras()
    keyboard = []
    for o in obras:
        keyboard.append([InlineKeyboardButton(
            f"{o['id']} · {o['nombre']}", callback_data=f"{prefix}|{o['id']}"
        )])
    keyboard.append([InlineKeyboardButton("➕ Nueva obra", callback_data=f"{prefix}|__NUEVA__")])
    if prefix != "nota_obra":
        pass  # nota no tiene GENERAL
    else:
        keyboard.append([InlineKeyboardButton("Sin obra específica", callback_data=f"{prefix}|GENERAL")])
    return keyboard


# ══════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════
AYUDA_TEXTO = (
    "⚙️ *KONSTRUKT — Comandos disponibles*\n\n"
    "📝 /nota — Guardar una nota\n"
    "✅ /nuevatarea — Crear una tarea\n"
    "📋 /seguimiento — Ver y actualizar tareas activas\n"
    "🏗️ /obra — Ver estado y etapas de una obra\n"
    "➕ /nuevaobra — Registrar una obra nueva\n"
    "👷 /personal — Ver personal asignado a una obra\n"
    "👤 /nuevopersonal — Agregar persona a una obra\n"
    "📊 /etapas — Ver\/actualizar % de avance de etapas\n"
    "📋 /resumen — Resumen general de todas las obras\n\n"
    "_Escribí el comando o usá el menú de abajo._"
)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AYUDA_TEXTO, parse_mode="Markdown")

async def ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AYUDA_TEXTO, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════
# /nuevaobra — Crear obra directamente
# ══════════════════════════════════════════════════════════
async def nuevaobra_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏗️ *Nueva obra*\n\n¿Cómo se llama la obra?", parse_mode="Markdown")
    return OBRA_NOMBRE

async def nuevaobra_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["obra_nombre"] = update.message.text
    await update.message.reply_text("👤 ¿Nombre del cliente?")
    return OBRA_CLIENTE

async def nuevaobra_cliente(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["obra_cliente"] = update.message.text
    await update.message.reply_text("📅 ¿Fecha de entrega? (ej: Dic 2025)")
    return OBRA_ENTREGA

async def nuevaobra_entrega(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    entrega = update.message.text
    nombre = ctx.user_data["obra_nombre"]
    cliente = ctx.user_data["obra_cliente"]
    inicio = datetime.now().strftime("%b %Y")

    obra_id = db.add_obra(nombre, cliente, inicio, entrega)
    ctx.user_data.clear()

    await update.message.reply_text(
        f"✅ *Obra creada* `{obra_id}`\n\n"
        f"🏗️ {nombre}\n"
        f"👤 Cliente: {cliente}\n"
        f"📅 Entrega: {entrega}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
# /nota
# ══════════════════════════════════════════════════════════
async def nota_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 *Nueva nota*\n\nEscribí el texto:", parse_mode="Markdown")
    return NOTA_TEXTO

async def nota_guardar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["nota_texto"] = update.message.text
    ctx.user_data["nota_autor"] = update.message.from_user.first_name
    ctx.user_data["nota_fecha"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    keyboard = keyboard_obras("nota_obra")
    await update.message.reply_text(
        "¿A qué obra vinculás esta nota?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return NOTA_OBRA_NUEVA_NOMBRE

async def nota_obra_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, obra_id = query.data.split("|", 1)

    if obra_id == "__NUEVA__":
        await query.edit_message_text("🏗️ ¿Cómo se llama la nueva obra?")
        ctx.user_data["nota_esperando_obra_nueva"] = True
        return NOTA_OBRA_NUEVA_NOMBRE

    texto = ctx.user_data.get("nota_texto", "")
    autor = ctx.user_data.get("nota_autor", "")
    fecha = ctx.user_data.get("nota_fecha", "")
    db.add_nota(autor, fecha, texto, obra_id)
    ctx.user_data.clear()

    await query.edit_message_text(
        f"✅ *Nota guardada*\n\n📌 Obra: `{obra_id}`\n✍️ {autor} · {fecha}\n\n_{texto[:100]}{'...' if len(texto)>100 else ''}_",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def nota_obra_nueva_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text
    inicio = datetime.now().strftime("%b %Y")
    obra_id = db.add_obra(nombre, "—", inicio, "—")

    texto = ctx.user_data.get("nota_texto", "")
    autor = ctx.user_data.get("nota_autor", "")
    fecha = ctx.user_data.get("nota_fecha", "")
    db.add_nota(autor, fecha, texto, obra_id)
    ctx.user_data.clear()

    await update.message.reply_text(
        f"✅ Obra `{obra_id}` creada y nota guardada.\n\n_{texto[:100]}{'...' if len(texto)>100 else ''}_",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
# /nuevatarea
# ══════════════════════════════════════════════════════════
async def tarea_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ *Nueva tarea*\n\nDescribí la tarea:", parse_mode="Markdown")
    return TAREA_DESC

async def tarea_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["tarea_desc"] = update.message.text
    keyboard = keyboard_obras("nt_obra")
    await update.message.reply_text("🏗️ ¿A qué obra pertenece?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TAREA_OBRA

async def tarea_obra_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, obra_id = query.data.split("|", 1)

    if obra_id == "__NUEVA__":
        await query.edit_message_text("🏗️ ¿Cómo se llama la nueva obra?")
        return TAREA_OBRA_NUEVA_NOMBRE

    obras = db.get_obras()
    obra = next((o for o in obras if o["id"] == obra_id), None)
    ctx.user_data["tarea_obra_id"] = obra_id
    ctx.user_data["tarea_obra_nombre"] = obra["nombre"] if obra else obra_id
    return await _pedir_persona(query, obra_id)

async def tarea_obra_nueva_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text
    inicio = datetime.now().strftime("%b %Y")
    obra_id = db.add_obra(nombre, "—", inicio, "—")
    ctx.user_data["tarea_obra_id"] = obra_id
    ctx.user_data["tarea_obra_nombre"] = nombre
    await update.message.reply_text(f"✅ Obra `{obra_id}` creada.")
    personal = db.get_personal_por_obra(obra_id)
    keyboard = [[InlineKeyboardButton("Sin asignar", callback_data="nt_persona|Sin asignar")]]
    await update.message.reply_text("👷 ¿A quién asignás la tarea?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TAREA_PERSONA

async def _pedir_persona(query_or_msg, obra_id: str):
    personal = db.get_personal_por_obra(obra_id)
    if not personal:
        keyboard = [[InlineKeyboardButton("Sin asignar", callback_data="nt_persona|Sin asignar")]]
    else:
        keyboard = [[InlineKeyboardButton(f"{p['nombre']} · {p['rol']}", callback_data=f"nt_persona|{p['nombre']}")] for p in personal]
        keyboard.append([InlineKeyboardButton("Sin asignar", callback_data="nt_persona|Sin asignar")])
    await query_or_msg.edit_message_text("👷 ¿A quién asignás la tarea?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TAREA_PERSONA

async def tarea_persona_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, persona = query.data.split("|", 1)
    ctx.user_data["tarea_persona"] = persona
    await query.edit_message_text("📅 ¿Fecha límite? (ej: 05/03 o 'sin fecha')")
    return TAREA_FECHA

async def tarea_fecha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fecha = update.message.text
    autor = update.message.from_user.first_name
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    tarea_id = db.add_tarea(
        desc=ctx.user_data["tarea_desc"],
        obra_id=ctx.user_data["tarea_obra_id"],
        persona=ctx.user_data["tarea_persona"],
        fecha=fecha,
        creado_por=autor,
        creado_en=ahora
    )
    await update.message.reply_text(
        f"✅ *Tarea creada* `{tarea_id}`\n\n"
        f"📋 {ctx.user_data['tarea_desc']}\n"
        f"🏗️ {ctx.user_data['tarea_obra_nombre']}\n"
        f"👷 {ctx.user_data['tarea_persona']}\n"
        f"📅 {fecha}",
        parse_mode="Markdown"
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
# /seguimiento
# ══════════════════════════════════════════════════════════
async def seguimiento(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tareas = db.get_tareas_activas()
    if not tareas:
        await update.message.reply_text("📋 No hay tareas activas.")
        return
    await update.message.reply_text(f"📋 *Tareas activas ({len(tareas)})*", parse_mode="Markdown")
    iconos = {"pendiente": "○", "iniciada": "▷", "completa": "✓", "incompleta": "✕"}
    for t in tareas[:15]:
        icono = iconos.get(t["status"], "○")
        texto = f"{icono} *{t['titulo']}*\n🏗️ {t['obra_id']} · 👷 {t['persona']} · 📅 {t['fecha']}\nEstado: `{t['status'].upper()}`"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▷ Iniciada", callback_data=f"seg|{t['id']}|iniciada"),
             InlineKeyboardButton("✓ Completa", callback_data=f"seg|{t['id']}|completa")],
            [InlineKeyboardButton("✕ Incompleta", callback_data=f"seg|{t['id']}|incompleta")]
        ])
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=keyboard)

async def seguimiento_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, tarea_id, nuevo_status = query.data.split("|")
    if nuevo_status == "incompleta":
        ctx.user_data["tarea_incompleta_id"] = tarea_id
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"✕ Tarea `{tarea_id}`\n\n¿Cuál es el motivo?", parse_mode="Markdown")
        return TAREA_INCOMPLETA_MOTIVO
    db.update_tarea_status(tarea_id, nuevo_status)
    emoji = "✅" if nuevo_status == "completa" else "🔄"
    await query.edit_message_text(query.message.text + f"\n\n{emoji} *{nuevo_status.upper()}*", parse_mode="Markdown")
    return ConversationHandler.END

async def tarea_incompleta_motivo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    motivo = update.message.text
    tarea_id = ctx.user_data.get("tarea_incompleta_id")
    autor = update.message.from_user.first_name
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    db.update_tarea_status(tarea_id, "incompleta", motivo)
    db.add_nota(autor, fecha, f"[TAREA {tarea_id} INCOMPLETA] {motivo}", "SEGUIMIENTO")
    await update.message.reply_text(f"✕ Tarea `{tarea_id}` incompleta.\n📝 Motivo guardado.", parse_mode="Markdown")
    ctx.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
# /obra
# ══════════════════════════════════════════════════════════
async def obra_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    obras = db.get_obras()
    if not obras:
        await update.message.reply_text("⚠️ No hay obras. Usá /nuevaobra para crear una.")
        return
    keyboard = [[InlineKeyboardButton(f"{o['id']} · {o['nombre']}", callback_data=f"obra_ver|{o['id']}")] for o in obras]
    await update.message.reply_text("🏗️ *¿Qué obra querés ver?*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def obra_ver_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, obra_id = query.data.split("|", 1)
    obra = db.get_obra_detalle(obra_id)
    if not obra:
        await query.edit_message_text("⚠️ Obra no encontrada.")
        return
    etapas = obra.get("etapas", [])
    etapas_txt = ""
    total = 0
    for e in etapas:
        filled = round(int(e["pct"]) / 10)
        barra = f"[{'█'*filled}{'░'*(10-filled)}] {e['pct']}%"
        etapas_txt += f"\n{barra} {e['nombre']}"
        total += int(e["pct"])
    avance = round(total / len(etapas)) if etapas else 0
    texto = (
        f"🏗️ *{obra['nombre']}* `{obra_id}`\n"
        f"Estado: `{obra.get('status','—').upper()}`\n"
        f"Avance: *{avance}%* · Entrega: {obra.get('entrega','—')}"
    )
    texto += f"\n\n*Etapas:*{etapas_txt}" if etapas_txt else "\n\n_Sin etapas cargadas._"
    await query.edit_message_text(texto, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════
# /personal
# ══════════════════════════════════════════════════════════
async def personal_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    obras = db.get_obras()
    if not obras:
        await update.message.reply_text("⚠️ No hay obras cargadas.")
        return
    keyboard = [[InlineKeyboardButton(f"{o['id']} · {o['nombre']}", callback_data=f"pers_obra|{o['id']}")] for o in obras]
    await update.message.reply_text("👷 *¿Personal de qué obra?*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def personal_obra_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, obra_id = query.data.split("|", 1)
    personal = db.get_personal_por_obra(obra_id)
    if not personal:
        await query.edit_message_text(f"👷 No hay personal asignado a `{obra_id}`.", parse_mode="Markdown")
        return
    lista = "\n".join([f"• *{p['nombre']}* · {p['rol']}" for p in personal])
    await query.edit_message_text(f"👷 *Personal en {obra_id}* ({len(personal)} personas)\n\n{lista}", parse_mode="Markdown")



# ══════════════════════════════════════════════════════════
# /nuevopersonal — Agregar persona a obra
# ══════════════════════════════════════════════════════════
PERS_NOMBRE, PERS_ROL, PERS_OBRA = range(11, 14)

async def nuevopersonal_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 *Nuevo personal*\n\n¿Nombre completo?", parse_mode="Markdown")
    return PERS_NOMBRE

async def nuevopersonal_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["pers_nombre"] = update.message.text
    await update.message.reply_text("🔧 ¿Rol? (ej: Soldador, Electricista, Capataz)")
    return PERS_ROL

async def nuevopersonal_rol(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["pers_rol"] = update.message.text
    obras = db.get_obras()
    if not obras:
        await update.message.reply_text("⚠️ No hay obras cargadas.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{o['id']} · {o['nombre']}", callback_data=f"np_obra|{o['id']}")] for o in obras]
    await update.message.reply_text("🏗️ ¿A qué obra asignás esta persona?", reply_markup=InlineKeyboardMarkup(keyboard))
    return PERS_OBRA

async def nuevopersonal_obra_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, obra_id = query.data.split("|", 1)
    nombre = ctx.user_data["pers_nombre"]
    rol = ctx.user_data["pers_rol"]
    obras = db.get_obras()
    obra = next((o for o in obras if o["id"] == obra_id), None)
    obra_nombre = obra["nombre"] if obra else obra_id
    db.add_personal(nombre, rol, obra_id, obra_nombre)
    ctx.user_data.clear()
    await query.edit_message_text(
        f"✅ *Personal agregado*\n\n👤 {nombre}\n🔧 {rol}\n🏗️ {obra_nombre}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
# /etapas — Ver y actualizar % de etapas
# ══════════════════════════════════════════════════════════
ETAPA_OBRA, ETAPA_SELECCION, ETAPA_PCT = range(14, 17)

async def etapas_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    obras = db.get_obras()
    if not obras:
        await update.message.reply_text("⚠️ No hay obras cargadas.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{o['id']} · {o['nombre']}", callback_data=f"et_obra|{o['id']}")] for o in obras]
    await update.message.reply_text("📊 *¿Etapas de qué obra?*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ETAPA_OBRA

async def etapas_obra_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, obra_id = query.data.split("|", 1)
    ctx.user_data["etapa_obra_id"] = obra_id
    etapas = db.get_etapas(obra_id)
    if not etapas:
        await query.edit_message_text(f"⚠️ No hay etapas cargadas para `{obra_id}`.\n\nCargalas en la pestaña Etapas de la Sheet.", parse_mode="Markdown")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{e['nombre']} — {e['pct']}%", callback_data=f"et_sel|{e['nombre']}")] for e in etapas]
    await query.edit_message_text("📊 ¿Qué etapa querés actualizar?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ETAPA_SELECCION

async def etapas_sel_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, etapa_nombre = query.data.split("|", 1)
    ctx.user_data["etapa_nombre"] = etapa_nombre
    await query.edit_message_text(f"📊 Etapa: *{etapa_nombre}*\n\n¿Nuevo % de avance? (0 a 100)", parse_mode="Markdown")
    return ETAPA_PCT

async def etapas_pct(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(update.message.text.replace("%","").strip())
        if not 0 <= pct <= 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Escribí un número entre 0 y 100.")
        return ETAPA_PCT
    obra_id = ctx.user_data["etapa_obra_id"]
    etapa_nombre = ctx.user_data["etapa_nombre"]
    db.update_etapa_pct(obra_id, etapa_nombre, pct)
    ctx.user_data.clear()
    await update.message.reply_text(
        f"✅ *{etapa_nombre}* actualizada a *{pct}%*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
# /resumen — Resumen de todas las obras
# ══════════════════════════════════════════════════════════
async def resumen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    obras = db.get_obras()
    if not obras:
        await update.message.reply_text("⚠️ No hay obras cargadas.")
        return
    tareas_activas = db.get_tareas_activas()
    texto = "📋 *RESUMEN DE OBRAS*\n\n"
    for o in obras:
        etapas = db.get_etapas(o["id"])
        if etapas:
            avance = round(sum(e["pct"] for e in etapas) / len(etapas))
        else:
            avance = 0
        filled = round(avance / 10)
        barra = f"[{'█'*filled}{'░'*(10-filled)}] {avance}%"
        tareas_obra = [t for t in tareas_activas if t.get("obra_id") == o["id"]]
        texto += f"🏗️ *{o['nombre']}* `{o['id']}`\n"
        texto += f"{barra}\n"
        texto += f"Estado: `{o.get('status','—').upper()}` · Entrega: {o.get('entrega','—')}\n"
        texto += f"Tareas activas: {len(tareas_obra)}\n\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(TOKEN).build()

    nuevaobra_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevaobra", nuevaobra_start)],
        states={
            OBRA_NOMBRE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevaobra_nombre)],
            OBRA_CLIENTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevaobra_cliente)],
            OBRA_ENTREGA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevaobra_entrega)],
        },
        fallbacks=[],
        allow_reentry=True
    )

    nota_conv = ConversationHandler(
        entry_points=[CommandHandler("nota", nota_start)],
        states={
            NOTA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, nota_guardar)],
            NOTA_OBRA_NUEVA_NOMBRE: [
                CallbackQueryHandler(nota_obra_callback, pattern="^nota_obra\\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, nota_obra_nueva_nombre),
            ],
        },
        fallbacks=[],
        allow_reentry=True
    )

    tarea_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevatarea", tarea_start)],
        states={
            TAREA_DESC:            [MessageHandler(filters.TEXT & ~filters.COMMAND, tarea_desc)],
            TAREA_OBRA:            [CallbackQueryHandler(tarea_obra_callback, pattern="^nt_obra\\|")],
            TAREA_OBRA_NUEVA_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tarea_obra_nueva_nombre)],
            TAREA_PERSONA:         [CallbackQueryHandler(tarea_persona_callback, pattern="^nt_persona\\|")],
            TAREA_FECHA:           [MessageHandler(filters.TEXT & ~filters.COMMAND, tarea_fecha)],
        },
        fallbacks=[],
        allow_reentry=True
    )

    seg_conv = ConversationHandler(
        entry_points=[
            CommandHandler("seguimiento", seguimiento),
            CallbackQueryHandler(seguimiento_callback, pattern="^seg\\|"),
        ],
        states={
            TAREA_INCOMPLETA_MOTIVO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tarea_incompleta_motivo)],
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(nuevaobra_conv)

    nuevopersonal_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevopersonal", nuevopersonal_start)],
        states={
            PERS_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevopersonal_nombre)],
            PERS_ROL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevopersonal_rol)],
            PERS_OBRA:   [CallbackQueryHandler(nuevopersonal_obra_callback, pattern="^np_obra\\|")],
        },
        fallbacks=[],
        allow_reentry=True
    )

    etapas_conv = ConversationHandler(
        entry_points=[CommandHandler("etapas", etapas_start)],
        states={
            ETAPA_OBRA:      [CallbackQueryHandler(etapas_obra_callback, pattern="^et_obra\\|")],
            ETAPA_SELECCION: [CallbackQueryHandler(etapas_sel_callback, pattern="^et_sel\\|")],
            ETAPA_PCT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, etapas_pct)],
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(nuevopersonal_conv)
    app.add_handler(etapas_conv)
    app.add_handler(nota_conv)
    app.add_handler(tarea_conv)
    app.add_handler(seg_conv)
    app.add_handler(CommandHandler("obra", obra_start))
    app.add_handler(CallbackQueryHandler(obra_ver_callback, pattern="^obra_ver\\|"))
    app.add_handler(CallbackQueryHandler(personal_obra_callback, pattern="^pers_obra\\|"))
    app.add_handler(CommandHandler("personal", personal_start))

    print("🤖 KONSTRUKT BOT corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
