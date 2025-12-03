import json
import os
import random
import subprocess
from difflib import get_close_matches

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

# Token del bot (da variabile d'ambiente)
TOKEN = os.getenv("TOKEN")

ADMIN_PASSWORD = "1234"  # Se poi vuoi usare comandi admin

# Configura GitHub
GITHUB_USERNAME = "aboutDani"  # Inserisci il tuo username di GitHub
GITHUB_REPO = "echobrain"      # Nome del repository dove vuoi salvare db.json
GIT_TOKEN = os.getenv("GIT_TOKEN")  # Token GitHub salvato su Railway/Render

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
    """Salva la knowledge base in un file JSON e lo pusha su GitHub."""
    with open(DB_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    push_to_github()  # Aggiorna il file su GitHub


def push_to_github():
    """Esegue il push di db.json su GitHub automaticamente."""
    if not GIT_TOKEN:
        print("❌ ERRORE: GIT_TOKEN non trovato nelle variabili d'ambiente")
        return

    repo_url = f"https://{GITHUB_USERNAME}:{GIT_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git"

    try:
        subprocess.run(["git", "config", "--global", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "config", "--global", "user.name", "Bot Auto Commit"], check=True)
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
        subprocess.run(["git", "add", "db.json"], check=True)
        subprocess.run(["git", "commit", "-m", "Auto update db.json"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ Database aggiornato su GitHub con successo!")
    except subprocess.CalledProcessError as e:
        print("❌ ERRORE nel push su GitHub:", e)


def find_best_match(user_question: str, questions: list) -> str | None:
    """Trova la domanda più simile tra quelle disponibili."""
    matches = get_close_matches(user_question, questions, n=1, cutoff=0.8)
    return matches[0] if matches else None


def get_answer_for_question(question: str, knowledge_base: dict) -> list:
    """Restituisce tutte le risposte disponibili per una domanda."""
    for q in knowledge_base["questions"]:
        if q["question"].lower() == question.lower():
            return q.get("answers", [])
    return []


async def start(update: Update, context: CallbackContext) -> None:
    """Messaggio di benvenuto quando si avvia il bot."""
    await update.message.reply_text(
        "👋 Ciao! Scrivi una domanda e proverò a rispondere! Digita /help per vedere i comandi."
    )


async def help_command(update: Update, context: CallbackContext) -> None:
    """Mostra la lista dei comandi disponibili."""
    help_text = (
        "📜 *Comandi disponibili:*\n"
        "/help - Mostra questo messaggio 📖\n"
        "/list - Mostra tutte le domande e risposte 📋\n"
        "👉 Scrivi una domanda e io proverò a rispondere!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def list_questions(update: Update, context: CallbackContext) -> None:
    """Mostra tutte le domande e risposte salvate nel database."""
    if not knowledge_base["questions"]:
        await update.message.reply_text("🤖 Non ci sono domande salvate nel database.")
        return

    message = "📋 *Lista delle domande e risposte:*\n\n"
    for i, q in enumerate(knowledge_base["questions"], 1):
        answers = "\n   - ".join(q["answers"]) if q["answers"] else "Nessuna risposta"
        message += f"{i}. *{q['question']}*\n   - {answers}\n\n"

    await update.message.reply_text(message, parse_mode="Markdown")


async def handle_message(update: Update, context: CallbackContext) -> None:
    """Risponde ai messaggi e apprende nuove risposte se necessario."""
    user_input = update.message.text.strip().lower()

    # Se l'utente ha già fatto una domanda, sta rispondendo con l'apprendimento
    if "waiting_for_answer" in context.user_data:
    user_question = context.user_data["waiting_for_answer"]
    user_answer = user_input_raw  # testo originale

    if user_answer.lower() in ("skip", "q"):
        await update.message.reply_text("⏭️ Nessuna risposta salvata. Proseguiamo!")
        del context.user_data["waiting_for_answer"]
        return

    # Aggiunge la nuova risposta nel database
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

    # Se la domanda esiste già, risponde
    best_match = find_best_match(
        user_input, [q["question"] for q in knowledge_base["questions"]]
    )

    if best_match:
        answers = get_answer_for_question(best_match, knowledge_base)
        if answers:
            response = random.choice(answers)
            await update.message.reply_text(f"🤖 {response}")
            return

    # Se non trova una risposta, chiede all'utente di insegnargliela con opzione "skip"
    await update.message.reply_text(
        "🤖 Non conosco la risposta. Digita la risposta per insegnarmela o 'skip/q' per uscire."
    )

    # Salva lo stato della domanda in attesa della risposta dell'utente
    context.user_data["waiting_for_answer"] = user_input


# Carico la knowledge base a livello globale
knowledge_base = load_knowledge_base()


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("❌ La variabile d'ambiente TOKEN non è impostata!")

    # Configura il bot con Application (sostituisce Updater)
    app = Application.builder().token(TOKEN).build()

    # Comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_questions))

    # Messaggi
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Avvia il bot
    print("🤖 Bot avviato in polling...")
    app.run_polling()

