# my-erp-crm: prenotazioni

Pagine pubbliche di prenotazione (modello Calendly) costruite sul calendario interno di
my-erp-crm. Un visitatore sceglie il tipo di appuntamento, la persona (o la lascia
assegnare), il giorno e l'ora nel proprio fuso orario, risponde alle domande e riceve
conferma, invito per il calendario, promemoria e un link per cancellare o riprogrammare.
Ogni prenotazione e' un evento nel calendario della persona che la riceve e, se si vuole,
un'opportunita' nel CRM.

## Cosa fa

| Funzione | Come |
|---|---|
| Tipi di appuntamento | Durata, fasce orarie settimanali, preavviso minimo, finestra di prenotazione, spaziatura, fuso orario, luogo (videochiamata, di persona, telefonata) |
| Persone | Una o piu' per tipo. Chi prenota sceglie la persona oppure l'orario e la persona e' assegnata automaticamente tra quelle libere (round-robin) |
| Disponibilita' reale | Gli slot si calcolano togliendo alle fasce gli impegni "occupato" del calendario di ogni persona: un blocco di tempo privato sparisce dal pubblico |
| Domande | Risposta breve, lunga, scelta da elenco, casella da spuntare; obbligatorie o no |
| Conferma manuale | La prenotazione resta in attesa e riserva l'orario; una persona interna la conferma o la cancella; chi la riceve ha un'attivita' da fare |
| Email | Conferma (con invito .ics), richiesta in attesa, nuovo orario, cancellazione; a chi prenota e a chi riceve |
| Promemoria | Quelli del calendario (email, notifica; SMS se il modulo e' installato), scelti per tipo |
| Gestione da parte di chi prenota | Link personale per vedere, riprogrammare o cancellare fino al preavviso impostato |
| CRM | Opzione "Crea opportunita'": una per prenotazione, assegnata alla persona che la riceve, con le risposte |
| Multi-sito | Ogni tipo si pubblica su un sito web preciso: tre domini, tre siti, un solo database |
| Anti-spam | Campo esca invisibile; se e' installato `website_cf_turnstile` (o `google_recaptcha`) il controllo compare da solo nel modulo |

## Indirizzi pubblici

| Indirizzo | Pagina |
|---|---|
| `/appointment` | Elenco dei tipi pubblicati sul sito (con un solo tipo, si apre direttamente) |
| `/appointment/<nome>-<id>` | Scelta della persona (se prevista) e calendario |
| `/appointment/<nome>-<id>/book?start=...` | Modulo di prenotazione |
| `/appointment/view/<token>` | Pagina personale di chi ha prenotato: dettagli, cambia orario, cancella |

L'indirizzo di ogni tipo e' nel campo "Indirizzo pubblico" della sua scheda.

## Installazione

1. Dopo la pubblicazione del ramo, in my-erp-crm: **Applicazioni** → cerca "prenotazioni" → **Installa**.
   Si installano da soli anche *Sito web*, *Calendario* e *CRM* se mancano.
2. **Impostazioni → Utenti**: a chi deve ricevere appuntamenti assegna "Prenotazioni / Utente";
   a chi crea i tipi "Prenotazioni / Responsabile".
3. Ogni persona: **Calendario → sincronizzazione** con Google o Outlook, se usa un calendario
   esterno. Serve una sola volta la configurazione in *Impostazioni → Integrazioni*.

## Un sito per dominio (es. cal.darpa.ch, flu.kliniksanktmoritz.ch, cal.kliniksanktmoritz.ch)

1. Sul server, in `/opt/my-erp-crm/.env`, aggiungi i domini a `DOMAIN` separati da virgola:
   `DOMAIN=erp.kliniksanktmoritz.ch, cal.kliniksanktmoritz.ch, flu.kliniksanktmoritz.ch, cal.darpa.ch`
   e rilancia `./aggiorna.sh`. Caddy ottiene da solo i certificati HTTPS per tutti.
2. Nel DNS di ciascun dominio: record `A` (o `CNAME`) del nome verso l'indirizzo del server,
   senza proxy di Cloudflare finche' il certificato non e' attivo.
3. **Sito web → Configurazione → Impostazioni** → attiva *Multi-sito*; poi **Nuovo sito web**:
   nome, dominio completo (`https://cal.darpa.ch`), tema. Ripeti per ogni dominio.
4. Per ogni sito, nelle stesse impostazioni: logo, lingue, e in *Homepage* l'indirizzo `/appointment`,
   cosi' il dominio apre direttamente l'elenco dei calendari.
5. In ogni tipo di appuntamento, campo *Sito web*: il sito su cui pubblicarlo. Poi **Pubblica**.

## Creare un tipo di appuntamento

**Prenotazioni → Tipi di appuntamento → Nuovo.**

1. Titolo, persone, assegnazione (scelta o automatica), dove.
2. Durata, intervallo tra gli orari, spaziatura, preavviso, finestra, limite di cancellazione, fuso orario.
3. Scheda *Orari*: una riga per fascia (due righe al giorno per lasciare la pausa pranzo).
4. Scheda *Domande*: quelle oltre a nome, email e telefono (sempre richiesti).
5. Scheda *Opzioni*: conferma manuale, ospiti, opportunita' CRM, promemoria.
6. Scheda *Messaggi*: introduzione e messaggio dopo la prenotazione.
7. Salva, **Apri la pagina pubblica** per provare (da loggato si vede anche se non pubblicato), poi **Pubblica**.

## Bloccare il tempo privato

Un evento nel calendario con stato "occupato" (anche ricorrente, es. ogni mattina dalle 7:30
alle 10:00 "Produzione contenuti") toglie quegli orari da tutti i calendari pubblici della
persona. Non serve altro.

## Sviluppo e test

```bash
./my-erp-crm --addons-path=addons -d prova -i my_erp_crm_appointment --test-enable --test-tags /my_erp_crm_appointment --stop-after-init
```

I test coprono il calcolo degli slot (fasce, impegni, spaziatura, inviti rifiutati, preavviso,
finestra, fusi orari), l'assegnazione automatica, la creazione della prenotazione con evento
e opportunita', la conferma manuale, la cancellazione, la riprogrammazione e le pagine
pubbliche (elenco, calendario, modulo, pagina personale).
