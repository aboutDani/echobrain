import json
import os
import random
import pyttsx3  # Libreria per la sintesi vocale
import tkinter as tk  # Libreria per l'interfaccia grafica
from tkinter import scrolledtext, messagebox, simpledialog  # Import di Tkinter
from difflib import get_close_matches

# Percorso del database JSON
DB_FILE = "db.json"

# Inizializza il motore di sintesi vocale
engine = pyttsx3.init()
voice_enabled = False  # Stato della voce (attivo di default)

def speak(text):
    """Fa parlare il bot solo se la modalità 'muto' non è attiva."""
    if voice_enabled:
        engine.say(text)
        engine.runAndWait()

def show_help():
    """Mostra una finestra con la legenda dei comandi disponibili."""
    help_text = (
        "📜 **Comandi disponibili:**\n"
        "- **muto** ➝ Disattiva la voce del bot 🔇\n"
        "- **parla** ➝ Riattiva la voce del bot 🔊\n"
        "- **rimuovi** ➝ Mostra la lista delle domande e permette di eliminarne una ❌\n"
        "- **lista** ➝ Mostra tutte le domande e le risposte salvate 📋\n"
        "- **quit** ➝ Chiude il chatbot 🛑\n\n"
        "👉 Scrivi un messaggio e il bot risponderà!"
    )
    messagebox.showinfo("Help - Comandi disponibili", help_text)

def load_knowledge_base(file_path: str) -> dict:
    """Carica la knowledge base da un file JSON."""
    if not os.path.exists(file_path):
        return {"questions": []}  
    
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        print("⚠️ Errore nel caricamento della knowledge base. Creando un nuovo file.")
        return {"questions": []}

def save_knowledge_base(file_path: str, data: dict):
    """Salva la knowledge base in un file JSON."""
    with open(file_path, 'w', encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

def find_best_match(user_question: str, questions: list[str]) -> str | None:
    """Trova la domanda più simile tra quelle disponibili."""
    matches = get_close_matches(user_question, questions, n=1, cutoff=0.8)
    return matches[0] if matches else None

def get_answer_for_question(question: str, knowledge_base: dict) -> list[str]:
    """Restituisce tutte le risposte disponibili per una domanda."""
    for q in knowledge_base["questions"]:
        if q["question"].lower() == question.lower():
            return q.get("answers", [])
    return []

def add_new_knowledge(user_input: str, knowledge_base: dict):
    """Permette di aggiungere una nuova domanda e risposta al database."""
    new_answer = simpledialog.askstring("Nuova risposta", "✍️ Digita la risposta o 'skip' per saltare:")

    if new_answer and new_answer.lower() != 'skip':
        knowledge_base["questions"].append({"question": user_input, "answers": [new_answer]})
        save_knowledge_base(DB_FILE, knowledge_base)
        update_chat(f'✅ Bot: Ho imparato una nuova risposta!', "bot")
        speak("Ho imparato una nuova risposta!")

def list_all_questions_and_answers():
    """Mostra tutte le domande e risposte salvate nel database."""
    if not knowledge_base["questions"]:
        update_chat("🤖 Bot: Non ci sono domande e risposte salvate nel database.", "bot")
        return

    message = "**📋 Lista delle domande e risposte salvate:**\n\n"
    for i, q in enumerate(knowledge_base["questions"], 1):
        answers = "\n   - ".join(q["answers"]) if q["answers"] else "Nessuna risposta salvata"
        message += f"{i}. **{q['question']}**\n   - {answers}\n\n"

    update_chat(message, "bot")

def remove_question():
    """Mostra la lista delle domande e permette di eliminare una selezionandone il numero."""
    questions = [q["question"] for q in knowledge_base["questions"]]
    
    if not questions:  
        update_chat("🤖 Bot: Non ci sono domande salvate nel database.", "bot")
        return

    # Mostra la lista delle domande
    message = "**📋 Domande salvate:**\n\n"
    for i, q in enumerate(questions, 1):
        message += f"{i}. {q}\n"
    
    update_chat(message, "bot")

    try:
        # Chiede il numero della domanda da eliminare
        question_index = simpledialog.askinteger("Rimuovi domanda", "📌 Inserisci il numero della domanda da eliminare (0 per annullare):")
        
        if question_index is None or question_index == 0:  
            update_chat("❌ Operazione annullata. Nessuna domanda è stata eliminata.", "bot")
            return
        
        question_index -= 1  # Per allinearsi agli indici della lista
        
        if 0 <= question_index < len(questions):
            question_to_remove = questions[question_index]
            knowledge_base["questions"] = [q for q in knowledge_base["questions"] if q["question"] != question_to_remove]
            save_knowledge_base(DB_FILE, knowledge_base)
            update_chat(f"❌ Bot: Ho rimosso la domanda '{question_to_remove}'.", "bot")
        else:
            update_chat("⚠️ Numero non valido! Inserisci un numero tra quelli mostrati.", "bot")
    
    except ValueError:
        update_chat("⚠️ Inserisci un numero valido!", "bot")

def send_message():
    """Invia il messaggio dell'utente al bot."""
    user_input = entry.get().strip().lower()
    if not user_input:
        return

    update_chat(f"Tu: {user_input}", "user")
    entry.delete(0, tk.END)  

    if user_input == "quit":
        root.quit()

    elif user_input == "muto":
        global voice_enabled
        voice_enabled = False
        update_chat("🔇 Bot: La voce è stata disattivata.", "bot")

    elif user_input == "parla":
        voice_enabled = True
        update_chat("🔊 Bot: La voce è stata riattivata.", "bot")
        speak("Ora posso parlare di nuovo.")

    elif user_input == "rimuovi":
        remove_question()

    elif user_input == "lista":
        list_all_questions_and_answers()

    else:
        best_match = find_best_match(user_input, [q["question"] for q in knowledge_base["questions"]])

        if best_match:
            answers = get_answer_for_question(best_match, knowledge_base)
            if answers:
                response = random.choice(answers)
                update_chat(f"🤖 Bot: {response}", "bot", speak_text=response)

        else:
            update_chat("🤖 Bot: Non conosco la risposta. Me lo insegni?", "bot")
            speak("Non conosco la risposta. Me lo insegni?")
            add_new_knowledge(user_input, knowledge_base)

def update_chat(message, sender="bot", speak_text=None):
    """Aggiorna la finestra di chat con un nuovo messaggio e poi avvia la sintesi vocale se necessario."""
    chat_area.config(state=tk.NORMAL)
    chat_area.insert(tk.END, f"{message}\n\n")
    chat_area.config(state=tk.DISABLED)
    chat_area.yview(tk.END)  

    # Se c'è un testo da far parlare, lo facciamo partire dopo 100ms
    if speak_text and voice_enabled:
        root.after(100, lambda: speak(speak_text))
 
def show_welcome_message():
    """Mostra un messaggio di benvenuto temporaneo nella chat."""
    welcome_message = "👋 Benvenuto! Scrivi un messaggio per iniziare. Clicca 'help' per vedere i comandi disponibili."
    chat_area.config(state=tk.NORMAL)
    chat_area.insert(tk.END, f"{welcome_message}\n\n", "welcome")  
    chat_area.config(state=tk.DISABLED)
    chat_area.yview(tk.END)  

    # Rimuove il messaggio dopo 5 secondi
    root.after(5000, remove_welcome_message)

def remove_welcome_message():
    """Rimuove il messaggio di benvenuto dalla chat."""
    chat_area.config(state=tk.NORMAL)
    chat_area.delete("1.0", "2.0")  # Elimina la prima riga (assumendo che il messaggio di benvenuto sia lì)
    chat_area.config(state=tk.DISABLED)

#cambio colore tema
def change_theme(theme):
    """Cambia il tema della chat."""
    themes = {
        "Scuro": {"bg": "#2C2C2C", "text": "white", "button": "#555555"},
        "Chiaro": {"bg": "#E6E6FA", "text": "black", "button": "#800080"},
        "Colorato": {"bg": "#FFD700", "text": "black", "button": "#FF4500"}
    }

    if theme in themes:
        root.configure(bg=themes[theme]["bg"])
        chat_area.configure(bg=themes[theme]["bg"], fg=themes[theme]["text"])
        entry.configure(bg=themes[theme]["bg"], fg=themes[theme]["text"])
        send_button.configure(bg=themes[theme]["button"], fg="white")
        help_button.configure(bg=themes[theme]["button"], fg="white")
        update_chat(f"🎨 Tema cambiato in {theme}!", "bot")

# Creazione della finestra principale con Tkinter
root = tk.Tk()
root.title("Chatbot")
root.geometry("500x600")
# Chiamare la funzione all'avvio
root.after(200, show_welcome_message)

# Frame per il bottone Help
top_frame = tk.Frame(root)
top_frame.pack(fill=tk.X)

# Bottone Help (in alto a destra)
help_button = tk.Button(top_frame, text="❓ Help", font=("Arial", 12), command=show_help)
help_button.pack(side=tk.RIGHT, padx=10, pady=5)

# Chat
chat_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 12))
chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Input
entry = tk.Entry(root, font=("Arial", 14))
entry.pack(padx=10, pady=5, fill=tk.X)
entry.focus_set() # per mettere subito il focus
entry.bind("<Return>", lambda event: send_message())  # per il tasto invia


send_button = tk.Button(root, text="Invia", font=("Arial", 14), command=send_message)
send_button.pack(pady=5)

knowledge_base = load_knowledge_base(DB_FILE)

#GESTIONE COLORI
root.configure(bg="#6A0DAD")  # Viola acceso
top_frame.configure(bg="#4B0082")  # Viola scuro
chat_area.configure(bg="#E6E6FA", fg="black")  # Chat con sfondo lavanda chiaro
entry.configure(bg="#E6E6FA", fg="black")  # Input con sfondo lavanda
send_button.configure(bg="#800080", fg="white", activebackground="#9932CC")  # Bottoni viola più scuro
help_button.configure(bg="#800080", fg="white", activebackground="#9932CC")



# Aggiungi il menu per selezionare il tema
theme_menu = tk.Menu(root)
theme_menu.add_command(label="Scuro", command=lambda: change_theme("Scuro"))
theme_menu.add_command(label="Chiaro", command=lambda: change_theme("Chiaro"))
theme_menu.add_command(label="Colorato", command=lambda: change_theme("Colorato"))
root.config(menu=theme_menu)


root.mainloop()
