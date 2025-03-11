import json
import os
import random
from difflib import get_close_matches
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters


TOKEN = os.getenv("TOKEN")  # Il token viene preso da Render


ADMIN_PASSWORD = "1234"  # Sostituisci con la tua password


# Percorso del database JSON
DB_FILE = "db.json"

def load_knowledge_base() -> dict:
    """Carica la knowledge base da un file JSON."""
    if not os.path.exists(DB_FILE):
        return {"questions": []}
    
    try:
        with open(DB_FILE, 'r', encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"questions": []}

def save_knowledge_base(data: dict):
    """Salva la knowledge base in un file JSON."""
    with open(DB_FILE, 'w', encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

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
    await update.message.reply_text("👋 Ciao! Scrivi una domanda e proverò a rispondere! Digita /help per vedere i comandi.")

async def help_command(update: Update, context: CallbackContext) -> None:
    """Mostra la lista dei comandi disponibili."""
    help_text = (
        "📜 **Comandi disponibili:**\n"
        "/help - Mostra questo messaggio 📖\n"
        "/list - Mostra tutte le domande e risposte 📋\n"
        "👉 Scrivi una domanda e io proverò a rispondere!"
    )
    await update.message.reply_text(help_text)

async def list_questions(update: Update, context: CallbackContext) -> None:
    """Mostra tutte le domande e risposte salvate nel database."""
    if not knowledge_base["questions"]:
        await update.message.reply_text("🤖 Non ci sono domande salvate nel database.")
        return

    message = "📋 **Lista delle domande e risposte:**\n\n"
    for i, q in enumerate(knowledge_base["questions"], 1):
        answers = "\n   - ".join(q["answers"]) if q["answers"] else "Nessuna risposta"
        message += f"{i}. **{q['question']}**\n   - {answers}\n\n"

    await update.message.reply_text(message)

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Risponde ai messaggi e apprende nuove risposte se necessario."""
    user_input = update.message.text.strip().lower()

    # Se l'utente ha già fatto una domanda, sta rispondendo con l'apprendimento
    if "waiting_for_answer" in context.user_data:
        user_question = context.user_data["waiting_for_answer"]
        user_answer = user_input

        if user_answer.lower() == "skip" or user_answer.lower() == "q":
            await update.message.reply_text("⏭️ Nessuna risposta salvata. Proseguiamo!")
            del context.user_data["waiting_for_answer"]
            return

        # Aggiunge la nuova risposta nel database
        for q in knowledge_base["questions"]:
            if q["question"].lower() == user_question.lower():
                q["answers"].append(user_answer)
                break
        else:
            # Se la domanda non esiste, la crea con la nuova risposta
            knowledge_base["questions"].append({"question": user_question, "answers": [user_answer]})

        save_knowledge_base(knowledge_base)  # Salva le nuove informazioni

        await update.message.reply_text(f"✅ Grazie! Ho memorizzato la risposta:\n\n**{user_question} ➝ {user_answer}**")

        # Rimuove lo stato di attesa
        del context.user_data["waiting_for_answer"]
        return

    # Se la domanda esiste già, risponde
    best_match = find_best_match(user_input, [q["question"] for q in knowledge_base["questions"]])
    
    if best_match:
        answers = get_answer_for_question(best_match, knowledge_base)
        if answers:
            response = random.choice(answers)
            await update.message.reply_text(f"🤖 {response}")
            return

    # Se non trova una risposta, chiede all'utente di insegnargliela con opzione "skip"
    await update.message.reply_text("🤖 Non conosco la risposta. Digita la risposta per insegnarmela o 'skip/q' per uscire.")

    # Salva lo stato della domanda in attesa della risposta dell'utente
    context.user_data["waiting_for_answer"] = user_input

## gestione password per il comando  /LIST
async def request_list_password(update: Update, context: CallbackContext) -> None:
    """Chiede una password prima di mostrare la lista."""
    await update.message.reply_text("🔒 Inserisci la password per accedere alla lista:")
    context.user_data["waiting_for_password"] = True  # Attiva lo stato di attesa della password

async def admin_list_questions(update: Update, context: CallbackContext) -> None:
    """Verifica la password e mostra la lista SOLO se è corretta."""
    if context.user_data.get("waiting_for_password"):  # Controlliamo se siamo in modalità password
        password_attempt = update.message.text

        if password_attempt == ADMIN_PASSWORD:
            await update.message.reply_text("✅ Password corretta! Ecco la lista delle domande:")

            # Mostra la lista delle domande
            knowledge_base = {"questions": []}
            if os.path.exists(DB_FILE):
                with open(DB_FILE, 'r', encoding="utf-8") as file:
                    knowledge_base = json.load(file)
            
            if not knowledge_base["questions"]:
                await update.message.reply_text("🤖 Non ci sono domande salvate nel database.")
            else:
                message = "📋 **Lista delle domande e risposte:**\n\n"
                for i, q in enumerate(knowledge_base["questions"], 1):
                    answers = "\n   - ".join(q["answers"]) if q["answers"] else "Nessuna risposta"
                    message += f"{i}. **{q['question']}**\n   - {answers}\n\n"

                await update.message.reply_text(message)

        else:
            await update.message.reply_text("❌ Password errata! Accesso negato.")

        del context.user_data["waiting_for_password"]  # IMPORTANTE: Rimuove lo stato di attesa della password
        return  # Blocca la registrazione del messaggio

    # Se il messaggio NON è una password, il bot gestisce normalmente la risposta
    await handle_message(update, context)

# Carica il database delle domande
knowledge_base = load_knowledge_base()

# Configura il bot con Application (sostituisce Updater)
app = Application.builder().token(TOKEN).build()

# Comandi
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
#app.add_handler(CommandHandler("list", list_questions))

# Messaggi
#app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# 🔹 Assicurati di collegare la funzione corretta
app.add_handler(CommandHandler("list", request_list_password))  # /list chiede la password
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_list_questions))  # Controlla la password



# Avvia il bot
app.run_polling()
