import json
import os
import random
from difflib import get_close_matches

import requests
from urllib.parse import quote

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

def format_answer_from_list(answers: list[str]) -> str:
    """
    Costruisce una risposta strutturata (Sintesi + Approfondimento),
    ignorando 'Collegamenti:'.
    """
    sintesi = None
    approfondimento = None
    altri = []

    for a in answers:
        low = a.lower()
        if low.startswith("sintesi:"):
            sintesi = a
        elif low.startswith("approfondimento:"):
            approfondimento = a
        elif low.startswith("collegamenti:"):
            # NON stampiamo i collegamenti
            continue
        else:
            altri.append(a)

    parts = []

    if sintesi:
        parts.append(f"📝 *Sintesi*\n{sintesi[len('Sintesi: '):]}")
    if approfondimento:
        parts.append(f"📚 *Approfondimento*\n{approfondimento[len('Approfondimento: '):]}")

    for extra in altri:
        parts.append(extra)

    # fallback se non trova niente di marcato
    if not parts:
        parts.append("\n".join(answers))

    return "\n\n".join(parts)

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "👋 Ciao! Scrivi una domanda! Digita /help per vedere i comandi."
    )


async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "📜 *Comandi disponibili:*\n"
        "/help - Mostra questo messaggio 📖\n"
        "/questions - Elenca solo le domande disponibili ❓\n"
        "/quiz - Avvia un quiz con domande casuali 🧠\n"
        "/stopquiz - Termina la modalità quiz 🛑\n"
        "/approfondisci [argomento] - Cerca info aggiuntive sul web 🌐\n"
        "/backup <password> - Fai il backup del json 🔐\n"
        "/delete <numero> - Elimina una domanda dal database 🗑️\n"
        "👉 Scrivi una domanda ..."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

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

async def approfondisci_command(update: Update, context: CallbackContext) -> None:
    """
    Recupera informazioni aggiuntive dal web (Wikipedia in italiano)
    sull'argomento richiesto o sull'ultima domanda riconosciuta.

    Modalità:
    - /approfondisci 42    -> usa la domanda n.42 del JSON
    - /approfondisci tuel  -> usa la stringa 'tuel'
    - /approfondisci       -> usa l'ultimo topic (last_topic)
    """
    query = None

    # 1) Se è stato passato qualcosa dopo il comando
    if context.args:
        first = context.args[0]

        # Caso: /approfondisci 42  -> prendo la domanda n.42
        if first.isdigit():
            index = int(first) - 1  # 1-based → 0-based
            if 0 <= index < len(knowledge_base["questions"]):
                q_obj = knowledge_base["questions"][index]
                base_query = q_obj.get("question", "").strip()
                if not base_query:
                    await update.message.reply_text(
                        "❌ Non trovo il testo della domanda per questo numero."
                    )
                    return
                query = base_query
            else:
                await update.message.reply_text(
                    "❌ Numero non valido. Controlla la lista con /questions."
                )
                return
        else:
            # Caso: /approfondisci tuel anticorruzione
            query = " ".join(context.args).strip()
    else:
        # 2) Nessun argomento passato → provo a usare l'ultimo best_match
        last_topic = context.user_data.get("last_topic")
        if not last_topic:
            await update.message.reply_text(
                "ℹ️ Usa: /approfondisci <argomento> oppure /approfondisci <numero_domanda>.\n"
                "Esempi:\n"
                "`/approfondisci tuel`\n"
                "`/approfondisci 42`\n\n"
                "Oppure fai prima una domanda, poi usa semplicemente `/approfondisci`.",
                parse_mode="Markdown"
            )
            return
        query = last_topic

    await update.message.reply_text(
        f"🌐 Cerco un approfondimento online su: *{query}* ...",
        parse_mode="Markdown"
    )

    # --- 1) CERCA SU WIKIPEDIA (API di ricerca) ---
    try:
        search_url = "https://it.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1,
        }
        search_resp = requests.get(search_url, params=search_params, timeout=5)

        if search_resp.status_code != 200:
            await update.message.reply_text(
                "❌ Non sono riuscito a cercare l'argomento su Wikipedia."
            )
            return

        search_data = search_resp.json()
        search_results = search_data.get("query", {}).get("search", [])

        if not search_results:
            await update.message.reply_text(
                "❌ Non ho trovato risultati su Wikipedia per questo argomento."
            )
            return

        # prendiamo il titolo della prima pagina trovata
        page_title = search_results[0].get("title")
        if not page_title:
            await update.message.reply_text(
                "❌ Non ho trovato un titolo valido su Wikipedia per questo argomento."
            )
            return

        # --- 2) CHIEDI IL RIASSUNTO DELLA PAGINA TROVATA ---
        summary_url = "https://it.wikipedia.org/api/rest_v1/page/summary/" + quote(page_title)
        summary_resp = requests.get(summary_url, timeout=5)

        if summary_resp.status_code != 200:
            await update.message.reply_text(
                "❌ Ho trovato una pagina ma non sono riuscito a leggerne il contenuto riassuntivo."
            )
            return

        data = summary_resp.json()
        title = data.get("title", page_title)
        extract = data.get("extract") or ""

        if not extract:
            await update.message.reply_text(
                "❌ La pagina trovata non contiene un testo riassuntivo utile."
            )
            return

        # Limitiamo un po' la lunghezza per non esplodere la chat
        max_len = 1800
        if len(extract) > max_len:
            extract = extract[:max_len].rsplit(" ", 1)[0] + "…"

        text = f"🌐 *Approfondimento web su: {title}*\n\n{extract}"
        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception:
        await update.message.reply_text(
            "⚠️ Si è verificato un errore cercando online l'approfondimento."
        )


async def quiz_command(update: Update, context: CallbackContext) -> None:
    """Avvia un quiz: il bot fa domande dal JSON e tu rispondi."""
    if not knowledge_base["questions"]:
        await update.message.reply_text("🤖 Il database è vuoto, non posso fare il quiz.")
        return

    # scegliamo una domanda a caso
    index = random.randrange(len(knowledge_base["questions"]))
    question_obj = knowledge_base["questions"][index]
    question_text = question_obj.get("question", "Domanda senza testo")

    # salviamo lo stato del quiz per l'utente
    context.user_data["quiz_mode"] = True
    context.user_data["quiz_index"] = index

    await update.message.reply_text(
        "🧠 *Quiz iniziato!*\n\n"
        f"Domanda n.{index + 1}:\n*{question_text}*\n\n"
        "✏️ Scrivi la tua risposta.\n"
        "⏭️ Scrivi *skip* per cambiare domanda.\n"
        "🛑 Digita /stopquiz per uscire dal quiz.",
        parse_mode="Markdown"
    )

async def stopquiz_command(update: Update, context: CallbackContext) -> None:
    """Termina la modalità quiz per l'utente."""
    if context.user_data.get("quiz_mode"):
        context.user_data.pop("quiz_mode", None)
        context.user_data.pop("quiz_index", None)
        await update.message.reply_text("🛑 Modalità quiz terminata. Torniamo alle domande normali.")
    else:
        await update.message.reply_text("🤖 Non sei in modalità quiz al momento.")

async def questions_command(update: Update, context: CallbackContext) -> None:
    """Elenca solo le domande disponibili nel database, senza le risposte."""
    if not knowledge_base["questions"]:
        await update.message.reply_text("🤖 Non ci sono domande salvate nel database.")
        return

    header = "📌 *Domande che puoi farmi:*\n\n"
    lines = []
    for i, q in enumerate(knowledge_base["questions"], 1):
        lines.append(f"{i}. {q['question']}")

    # Spezziamo in più messaggi se troppo lungo (telegram max 4096 chars)
    MAX_LEN = 3800
    current_block = header

    for line in lines:
        if len(current_block) + len(line) + 2 > MAX_LEN:
            await update.message.reply_text(current_block, parse_mode="Markdown")
            current_block = ""
        current_block += line + "\n"

    if current_block.strip():
        await update.message.reply_text(current_block, parse_mode="Markdown")

    # 🔹 attiva la modalità "scegli per numero" per il prossimo messaggio
    context.user_data["questions_mode"] = True
    await update.message.reply_text(
        "ℹ️ Adesso puoi inviarmi il *numero* di una domanda (es. `42`) per vedere la risposta.\n"
        "Se scrivi qualcos'altro, torniamo alla modalità normale.",
        parse_mode="Markdown"
    )

async def delete_command(update: Update, context: CallbackContext) -> None:
    """Elimina una domanda (e le sue risposte) in base al numero mostrato da /questions."""
    if not knowledge_base["questions"]:
        await update.message.reply_text("🤖 Il database è vuoto, non c'è nulla da eliminare.")
        return

    # Controllo argomento: /delete <numero>
    if not context.args:
        await update.message.reply_text("❌ Usa: /delete <numero_domanda>\nEsempio: /delete 3")
        return

    raw_index = context.args[0]

    try:
        index = int(raw_index)
    except ValueError:
        await update.message.reply_text("❌ Il parametro deve essere un numero intero. Esempio: /delete 3")
        return

    # /questions numerava da 1, quindi convertiamo in indice di lista (0-based)
    index -= 1

    if index < 0 or index >= len(knowledge_base["questions"]):
        await update.message.reply_text("❌ Numero non valido. Controlla la lista con /questions.")
        return

    # Prendiamo la domanda che stiamo per eliminare
    removed_question = knowledge_base["questions"].pop(index)

    # Salviamo il JSON aggiornato
    save_knowledge_base(knowledge_base)

    q_text = removed_question.get("question", "Domanda sconosciuta")

    await update.message.reply_text(
        f"🗑️ Ho eliminato la domanda n.{index + 1}:\n\n*{q_text}*",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Risponde ai messaggi e apprende nuove risposte se necessario."""
    if not update.message or not update.message.text:
        return

    user_input_raw = update.message.text.strip()
    user_input = user_input_raw.lower()

    # --- MODALITÀ: SCELTA DOMANDA PER NUMERO DOPO /questions ---
    if context.user_data.get("questions_mode"):
        # se è solo un numero, interpretiamolo come indice della domanda
        if user_input_raw.isdigit():
            index = int(user_input_raw) - 1  # /questions è 1-based
            if 0 <= index < len(knowledge_base["questions"]):
                q_obj = knowledge_base["questions"][index]
                q_text = q_obj.get("question", "Domanda senza testo")
                answers = q_obj.get("answers", [])

                formatted = format_answer_from_list(answers)

                await update.message.reply_text(
                    f"❓ *Domanda n.{index + 1}:* {q_text}\n\n{formatted}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "❌ Numero non valido. Controlla la lista con /questions."
                )

            # in ogni caso consumiamo la modalità
            context.user_data.pop("questions_mode", None)
            return
        else:
            # non è un numero → esco dalla modalità e procedo normale
            context.user_data.pop("questions_mode", None)
            # e continuo con la logica sotto (apprendimento / domanda)

    # --- MODALITÀ QUIZ ---
    if context.user_data.get("quiz_mode"):
        # comandi rapidi dentro il quiz
        if user_input in ("/stopquiz", "stop", "esci", "fine", "quit"):
            context.user_data.pop("quiz_mode", None)
            context.user_data.pop("quiz_index", None)
            await update.message.reply_text("🛑 Modalità quiz terminata. Torniamo alle domande normali.")
            return

        # salto domanda
        if user_input in ("skip", "s"):
            if not knowledge_base["questions"]:
                await update.message.reply_text("🤖 Database vuoto, non posso cambiare domanda.")
                return

            new_index = random.randrange(len(knowledge_base["questions"]))
            context.user_data["quiz_index"] = new_index
            question_obj = knowledge_base["questions"][new_index]
            question_text = question_obj.get("question", "Domanda senza testo")

            await update.message.reply_text(
                f"⏭️ Nuova domanda n.{new_index + 1}:\n*{question_text}*",
                parse_mode="Markdown",
            )
            return

        # risposta normale del quiz
        idx = context.user_data.get("quiz_index")
        if idx is None or idx < 0 or idx >= len(knowledge_base["questions"]):
            await update.message.reply_text("⚠️ Qualcosa è andato storto con il quiz. Riprova con /quiz.")
            context.user_data.pop("quiz_mode", None)
            context.user_data.pop("quiz_index", None)
            return

        question_obj = knowledge_base["questions"][idx]
        question_text = question_obj.get("question", "Domanda senza testo")
        answers = question_obj.get("answers", [])

        # mostriamo la risposta dell'utente + la soluzione ufficiale
        solution = format_answer_from_list(answers)

        await update.message.reply_text(
            f"✏️ *La tua risposta:*\n{user_input_raw}",
            parse_mode="Markdown"
        )

        await update.message.reply_text(
            f"✅ *Soluzione ufficiale per la domanda n.{idx + 1}:*\n*{question_text}*\n\n{solution}",
            parse_mode="Markdown"
        )

        # subito una nuova domanda
        new_index = random.randrange(len(knowledge_base["questions"]))
        context.user_data["quiz_index"] = new_index
        new_q = knowledge_base["questions"][new_index].get("question", "Domanda senza testo")

        await update.message.reply_text(
            f"🧠 Prossima domanda n.{new_index + 1}:\n*{new_q}*\n\n"
            "✏️ Scrivi la tua risposta oppure *skip* per passare.\n"
            "🛑 /stopquiz per uscire.",
            parse_mode="Markdown"
        )
        return

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
            response = format_answer_from_list(answers)

            # 🔹 salvo l'ultimo argomento trovato, per /approfondisci
            context.user_data["last_topic"] = best_match

            await update.message.reply_text(f"🤖 {response}", parse_mode="Markdown")
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
    app.add_handler(CommandHandler("questions", questions_command))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("stopquiz", stopquiz_command))
    app.add_handler(CommandHandler("approfondisci", approfondisci_command))

    # Messaggi normali
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot avviato in polling...")
    app.run_polling()











