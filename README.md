-------------------------------------------------------------------------------------------------------------------------

Il progetto è un Bot Telegram progettato per la gestione interattiva di quiz e argomenti, 
con un'architettura che ne permette il deployment online gratuito e continuativo utilizzando la piattaforma Railway.app.
L'idea è nata dall'agevolarmi lo studio per concorsi pubblici o esami in generale.

-------------------------------------------------------------------------------------------------------------------------

Architettura e Hosting

    Hosting Gratuito: Il bot è ospitato su Railway.app, che offre un piano gratuito per l'esecuzione del servizio, 
    garantendo che sia sempre accessibile online tramite Telegram senza costi di infrastruttura.
    Volatilità dei Dati: È fondamentale capire che, utilizzando il livello gratuito di Railway senza un database persistente dedicato,
    ogni riavvio del contenitore (gestito automaticamente da Railway o durante gli aggiornamenti) cancella tutte le modifiche apportate al file JSON originale.
    (Da qui l'idea di creare un comando backup json, così da avere la versione attuale disponibile in locale).

Funzionalità e Comandi
Il bot gestisce le interazioni tramite un file JSON iniziale popolabile e offre i seguenti comandi principali:

    /help: Mostra l'elenco dei comandi disponibili.
    /questions: Elenca tutte le domande caricate.
    /questions <parola>: Filtra le domande in base a una parola chiave.
    /quiz: Avvia una sessione interattiva di quiz con domande casuali.
    /stopquiz: Termina la sessione di quiz corrente.
    /flash: Avvia la modalità flashcard veloce.
    /stopflash: Termina la modalità flashcard.
    /backup <password>: Permette di scaricare una copia del file JSON attuale (necessario per salvare i dati prima di un riavvio).
    /delete <numero>: Elimina una specifica domanda dal set di dati corrente.

Sviluppi Futuri (TODO)
Il progetto è in fase di sviluppo e prevede le seguenti evoluzioni:

    - Sicurezza e Limiti: Implementare limiti e autenticazioni per chi può aggiungere o modificare domande, migliorando la sicurezza generale.
    - Integrazione QR Code: Collegare il bot a un sistema funzionante di QR Code (probabilmente sfruttando le funzioni native di Telegram).
    - Statistiche: Aggiungere un modulo per tracciare l'utilizzo e le statistiche degli utenti.
    - Dinamicità Fonte Dati: Riprogettare il sistema per facilitare il cambio della fonte dati 
                           (ad esempio, passando da JSON ad un altro JSON).
    
