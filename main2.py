import json
import os
import random
from difflib import get_close_matches

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

# Token del bot (da variabile d'ambiente)
TOKEN = os.getenv("TOKEN")

# per il backup
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")  # meglio da env, ma ha default

# Percorso del database JSON
DB_FILE = "db.json"


def load_knowledge_base() -> dict:
    """Carica la knowledge base da un file JSON."""
    if not os.path.exists(DB_FILE):
        return {"questions": []}

    try:
        with open(DB_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"questions": []}

def save_knowledge_base(data: dict):
    """Salva la knowledge base nel file JSON locale."""
    with open(DB_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

def find_best_match(user_question: str, knowledge_base: dict) -> str | None:
    """
    Trova la domanda migliore:
    1) per parola chiave nella domanda,
    2) poi nelle risposte,
    3) poi fuzzy match,
    usando uno score.
    """

    user = user_question.lower().strip()

    best_q = None
    best_score = 0

    # 1) Scoring manuale su tutte le domande
    for q in knowledge_base["questions"]:
        q_text = q["question"].lower()
        answers = [a.lower() for a in q.get("answers", [])]

        score = 0

        # parola chiave nel testo della domanda
        if user in q_text:
            score += 5

        # parola chiave nelle risposte
        if any(user in a for a in answers):
            score += 3

        # preferisci domande corte per definizioni (es. "Cos'è il TUEL?")
        score -= len(q_text) / 200.0  # penalità piccola per le domande molto lunghe

        # se questa domanda ha punteggio migliore, tienila
        if score > best_score:
            best_score = score
            best_q = q["question"]

    # Se abbiamo trovato qualcosa con score > 0, usiamo quello
    if best_q and best_score > 0:
        return best_q

    # 2) Se proprio nulla, usiamo fuzzy match sul testo delle domande
    questions_texts = [q["question"] for q in knowledge_base["questions"]]
    matches = get_close_matches(user_question, questions_texts, n=1, cutoff=0.4)
    return matches[0] if matches else None


def get_answer_for_question(question: str, knowledge_base: dict) -> list:
    """Restituisce tutte le risposte disponibili per una domanda."""
    for q in knowledge_base["questions"]:
        if q["question"].lower() == question.lower():
            return q.get("answers", [])
    return []


async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "👋 Ciao! Scrivi una domanda e proverò a rispondere! Digita /help per vedere i comandi."
    )


async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "📜 *Comandi disponibili:*\n"
        "/help - Mostra questo messaggio 📖\n"
        "/list - Mostra tutte le domande e risposte 📋\n"
        "/backup <password> - Fai il backup del json 🔐\n"
        "👉 Scrivi una domanda e io proverò a rispondere!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def list_questions(update: Update, context: CallbackContext) -> None:
    if not knowledge_base["questions"]:
        await update.message.reply_text("🤖 Non ci sono domande salvate nel database.")
        return

    message = "📋 *Lista delle domande e risposte:*\n\n"
    for i, q in enumerate(knowledge_base["questions"], 1):
        answers = "\n   - ".join(q["answers"]) if q["answers"] else "Nessuna risposta"
        message += f"{i}. *{q['question']}*\n   - {answers}\n\n"

    await update.message.reply_text(message, parse_mode="Markdown")

async def backup(update: Update, context: CallbackContext) -> None:
    """Invia il file db.json reale usato dal bot, protetto da password."""
    # Controllo password: /backup <password>
    if not context.args:
        await update.message.reply_text("🔐 Usa: /backup <password>")
        return

    supplied_password = context.args[0]

    if supplied_password != ADMIN_PASSWORD:
        await update.message.reply_text("⛔ Password errata.")
        return

    # Ok, password corretta → invio il file
    if not os.path.exists(DB_FILE):
        await update.message.reply_text("⚠️ Nessun database trovato.")
        return
    
    await update.message.reply_document(
        document=open(DB_FILE, "rb"),
        filename="db.json",
        caption="📦 Backup del database attuale"
    )

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Risponde ai messaggi e apprende nuove risposte se necessario."""
    if not update.message or not update.message.text:
        return

    user_input_raw = update.message.text.strip()
    user_input = user_input_raw.lower()

    # --- MODALITÀ APPRENDIMENTO ---
    if "waiting_for_answer" in context.user_data:
        user_question = context.user_data["waiting_for_answer"]
        user_answer = user_input_raw  # manteniamo il testo originale

        # Skip o annulla
        if user_answer.lower() in ("skip", "q"):
            await update.message.reply_text("⏭️ Proseguiamo!")
            del context.user_data["waiting_for_answer"]
            return

        # Aggiungi la risposta
        for q in knowledge_base["questions"]:
            if q["question"].lower() == user_question.lower():
                q["answers"].append(user_answer)
                break
        else:
            knowledge_base["questions"].append(
                {"question": user_question, "answers": [user_answer]}
            )

        save_knowledge_base(knowledge_base)

        await update.message.reply_text(
            f"✅ Grazie! Ho memorizzato la risposta:\n\n*{user_question} ➝ {user_answer}*",
            parse_mode="Markdown",
        )

        del context.user_data["waiting_for_answer"]
        return

    # --- DOMANDA NORMALE ---
    best_match = find_best_match(user_input, knowledge_base)

    if best_match:
        answers = get_answer_for_question(best_match, knowledge_base)
        if answers:
            response = random.choice(answers)
            await update.message.reply_text(f"🤖 {response}")
            return

    # Non trovata → chiedi risposta
    await update.message.reply_text(
        "🤖 Non conosco la risposta. Digita la risposta per insegnarmela poi 'skip/q' per uscire."
    )

    context.user_data["waiting_for_answer"] = user_input_raw


# Carico il DB a livello globale
knowledge_base = load_knowledge_base()


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("❌ La variabile d'ambiente TOKEN non è impostata!")

    app = Application.builder().token(TOKEN).build()

    # Comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_questions))
    app.add_handler(CommandHandler("backup", backup))

    # Messaggi normali
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot avviato in polling...")
    app.run_polling()




