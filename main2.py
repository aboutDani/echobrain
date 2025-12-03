import json
import os
import random
import subprocess
from difflib import get_close_matches

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

# Token del bot (da variabile d'ambiente)
TOKEN = os.getenv("TOKEN")

# Configura GitHub
GITHUB_USERNAME = "aboutDani"
GITHUB_REPO = "echobrain"
GIT_TOKEN = os.getenv("GIT_TOKEN")

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
        print("⚠️ GIT_TOKEN non trovato, salto il push su GitHub")
        return

    repo_url = f"https://{GITHUB_USERNAME}:{GIT_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git"

    try:
        subprocess.run(["git", "config", "--global", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "config", "--global", "user.name", "Bot Auto Commit"], check=True)
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
        subprocess.run(["git", "add", "db.json"], check=True)

        commit = subprocess.run(["git", "commit", "-m", "Auto update db.json"], capture_output=True, text=True)
        if "nothing to commit" in commit.stdout.lower():
            print("ℹ️ Nessuna modifica da salvare su GitHub")
            return

        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ Database aggiornato su GitHub con successo!")
    except subprocess.CalledProcessError as e:
        print("❌ ERRORE nel push su GitHub:", e)


def find_best_match(user_question: str, questions: list) -> str | None:
    """Trova la domanda più simile tra quelle disponibili."""
    matches = get_close_matches(user_question, questions, n=1, cutoff=0.6)
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
            await update.message.reply_text("⏭️ Nessuna risposta salvata. Proseguiamo!")
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
    best_match = find_best_match(
        user_input, [q["question"] for q in knowledge_base["questions"]]
    )

    if best_match:
        answers = get_answer_for_question(best_match, knowledge_base)
        if answers:
            response = random.choice(answers)
            await update.message.reply_text(f"🤖 {response}")
            return

    # Non trovata → chiedi risposta
    await update.message.reply_text(
        "🤖 Non conosco la risposta. Digita la risposta per insegnarmela o 'skip/q' per uscire."
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

    # Messaggi normali
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot avviato in polling...")
    app.run_polling()
