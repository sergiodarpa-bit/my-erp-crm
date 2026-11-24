# Posta in uscita

my-erp-crm scrive ai clienti: conferme dei moduli del sito, preventivi, fatture, richieste di
firma, avvisi interni. Tutto passa da **un server di posta in uscita** (SMTP, il protocollo con
cui un programma consegna un'email al fornitore di posta). Finché questa pagina non è
completata e provata, **nessuna email parte**, e il gestionale non lo dice a nessuno: le email
restano in errore nella coda.

Questa pagina vale per ogni installazione. Per la **versione SaaS** (un cliente, una sua
installazione o una sua azienda) è una voce obbligatoria dell'attivazione: vedi in fondo.

## Le tre regole, in breve

1. **Si entra con una casella vera.** Un reindirizzamento (alias, inoltro) non ha una password
   e non può autenticarsi: il fornitore risponde `535 Authentication failed`.
2. **Il mittente deve essere dello stesso dominio della casella con cui si entra.** Molti
   fornitori rifiutano un'email il cui mittente è di un altro dominio:
   `550 5.7.1 From header domain does not align with authenticated domain`.
3. **«Prova connessione» non basta.** Prova solo l'accesso. La posta è a posto quando
   un'email vera è arrivata nella casella di un destinatario esterno.

## Che cosa serve dal fornitore di posta

| Dato | Esempio |
|---|---|
| Server SMTP e porta | `smtp.esempio.net`, porta 465 |
| Crittografia | SSL/TLS (porta 465) oppure STARTTLS (porta 587) |
| Casella con cui entrare | `ufficio@azienda.example` (una casella vera, con la sua password) |
| Indirizzo che i clienti vedono | `info@azienda.example` (può essere un reindirizzamento, **dello stesso dominio**) |

La password non si scrive in documenti, messaggi o righe di comando: si digita solo nel campo
del gestionale.

## Passo 1 — Il server di posta

**Impostazioni → Funzioni tecniche → Email → Server posta in uscita → Nuovo** (serve la
modalità sviluppatore).

| Campo | Valore |
|---|---|
| Nome | un nome a piacere, per esempio quello del fornitore |
| Filtro mittente | l'indirizzo che i clienti vedono (`info@azienda.example`) oppure il solo dominio (`azienda.example`) |
| Autentica con | Nome utente |
| Server SMTP, Porta SMTP, Crittografia connessione | quelli del fornitore |
| Nome utente | la **casella vera** (`ufficio@azienda.example`) |
| Password | la password di quella casella, digitata a mano |

Attenzione al browser: spesso riempie da solo Nome utente e Password con le credenziali
salvate per entrare nel gestionale. Si controllano i due campi prima di salvare.

Poi **Prova connessione**: deve riuscire. Se risponde `535`, nome utente o password non sono
quelli di una casella vera di quel fornitore.

## Passo 2 — L'indirizzo predefinito del gestionale

Senza questo passo il gestionale spedisce con un mittente tecnico di un altro dominio, e il
fornitore rifiuta (regola 2). Il «Filtro mittente» da solo non sostituisce il mittente.

**Impostazioni → Funzioni tecniche → Email → Domini alias → Nuovo.**

| Campo | Valore |
|---|---|
| Nome | il dominio della posta, scritto per intero: `azienda.example` |
| Alias del mittente predefinito (in italiano compare come «Predefinito dall'alias») | la parte prima della chiocciola dell'indirizzo che i clienti vedono: `info` |
| Alias di rimbalzo | `bounce` (lasciare) |
| Alias catchall | `catchall` (lasciare) |

Il dominio creato si collega da solo all'azienda che non ne ha uno. Da questo momento ogni
email il cui mittente non è accettato dal server parte come `info@azienda.example`.

Si controlla l'indirizzo completo che la pagina mostra **prima** di salvare: un dominio scritto
male (una lettera, un punto) produce un mittente di un dominio che non esiste, e il fornitore
rifiuta di nuovo.

## Passo 3 — I tre reindirizzamenti dal fornitore

Con il dominio impostato, le risposte e i ritorni usano indirizzi che devono esistere dal
fornitore di posta, come caselle o come reindirizzamenti verso una casella letta da qualcuno:

| Indirizzo | A che cosa serve |
|---|---|
| quello del mittente predefinito (`info@…`) | le risposte dei clienti |
| `catchall@…` | le risposte alle email del gestionale legate a un documento |
| `bounce@…` | i ritorni delle email non consegnate |

Senza, quelle risposte si perdono in silenzio.

## Passo 4 — La prova vera

1. Si fa partire un'email vera verso una casella esterna (per esempio un invio dal modulo
   Contatti del sito, o un preventivo di prova).
2. Si guarda **nella casella del destinatario** che sia arrivata, e con quale mittente.
3. Si guarda la coda: **Impostazioni → Funzioni tecniche → Email → Email**. Nessuna riga deve
   essere in stato di errore; la colonna del motivo dice perché.

Le email fallite prima della correzione **non ripartono da sole**: si riaprono da quella
pagina e si rimandano, oppure si rifà l'azione che le aveva generate.

## Gli errori, e che cosa vogliono dire

| Che cosa si legge | Causa | Rimedio |
|---|---|---|
| `535 5.7.1 Authentication failed` | si sta entrando con un reindirizzamento, con una password sbagliata, o con campi riempiti dal browser | Passo 1: casella vera, password digitata a mano |
| `550 5.7.1 … From header domain does not align with authenticated domain` (arriva come email di mancata consegna alla casella con cui si entra) | il mittente è di un altro dominio | Passo 2 |
| nel registro: `No mail server matches the from_filter, using … as fallback` | nessun indirizzo predefinito, o filtro che non lo comprende | Passo 2, poi il Filtro mittente del Passo 1 |
| «Prova connessione» riesce ma le email non arrivano | la prova controlla solo l'accesso | Passo 4 |

## I moduli che scrivono ai clienti

Un modulo che riceve una richiesta dal sito e manda una conferma **non spedisce dentro la
richiesta**: mette l'email in coda e sveglia la coda. Così chi compila il modulo non aspetta il
server di posta, e una posta ferma non diventa un errore sulla pagina del sito. La conseguenza
è che un difetto della posta **non si vede dal sito**: il modulo risponde «ricevuto» e la
conferma non parte. Per questo il Passo 4 si rifà dopo ogni cambio di fornitore, di casella o
di password.

## Versione SaaS: la voce di attivazione di ogni cliente

Ogni cliente ha il **suo** dominio di posta, e le sue email devono partire a suo nome: non si
usa mai la casella di un altro cliente né quella di chi gestisce il servizio. Prima di
consegnare un'installazione:

- [ ] il cliente ha indicato una **casella vera** del suo dominio con cui entrare, e
      l'indirizzo che i suoi clienti devono vedere (stesso dominio);
- [ ] Passo 1 fatto, «Prova connessione» riuscita;
- [ ] Passo 2 fatto, dominio riletto lettera per lettera;
- [ ] Passo 3: i tre indirizzi esistono dal suo fornitore;
- [ ] Passo 4: un'email vera è arrivata in una casella esterna, col mittente giusto;
- [ ] la coda delle email non ha righe in errore;
- [ ] la password è stata digitata dal cliente o da chi ne ha titolo, e non compare in nessun
      documento, messaggio o riga di comando.

Finché una di queste voci è aperta, i moduli che scrivono ai clienti (conferme del sito,
preventivi, firma dei documenti) non si considerano in servizio.
