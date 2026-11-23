# Firma dei documenti (modulo `sign_oca`)

Il modulo **Firma** permette di far firmare un PDF qualsiasi (consenso informato, contratto,
modulo di accettazione) a pazienti, clienti o colleghi. Chi firma riceve un'email con un link,
apre il documento sul telefono o sul computer, compila i campi e firma con il dito o con il
mouse. Non serve un account.

Il modulo viene dalla Odoo Community Association (OCA), progetto
[OCA/sign](https://github.com/OCA/sign), licenza **AGPL-3** (vedi [NOTICE.md](../NOTICE.md)).

## Installazione

1. **Applicazioni** → togli il filtro "Applicazioni" → cerca `sign_oca` (nome mostrato:
   *Firma OCA*) → **Installa**.
2. L'amministratore ha già il ruolo *Firma: Amministratore*. Agli altri utenti lo assegni da
   **Impostazioni → Utenti → Firma**:

   | Ruolo | Cosa può fare |
   |---|---|
   | Utente: solo i propri documenti | crea e invia richieste, vede quelle che segue o firma |
   | Utente: tutti i documenti | come sopra, e vede tutte le richieste |
   | Amministratore | gestisce anche modelli, campi, ruoli e impostazioni |

3. **Firma → Impostazioni**: consigliato attivare *Invia ai firmatari una copia del documento
   firmato*. Senza questa opzione chi firma non riceve il PDF per email, ma può comunque
   scaricarlo dalla pagina che vede dopo la firma.

## Preparare un modello

**Firma → Modelli → Nuovo.**

1. Nome (es. "Consenso informato trattamento X") e il PDF.
2. **Configura**: si apre il PDF. Clic **destro** nel punto in cui va un campo e scegli il tipo:
   *Nome, E-mail, Telefono, Testo, Firma, Casella di spunta*.
3. Trascina e ridimensiona il campo. Clic sul campo per scegliere il **ruolo** (chi lo compila,
   es. *Cliente*) e se è **obbligatorio**. Il pulsante di conferma compare a chi firma solo
   quando tutti i campi obbligatori sono compilati.

## Inviare un documento da firmare

Dal modello: **Invia alla firma** → per ogni ruolo scegli la persona (es. il paziente) →
messaggio facoltativo → **Genera e firma**.

Il paziente riceve "Nuovo documento da firmare" con il link. Sulla pagina: *Fare clic per
iniziare* lo porta da un campo all'altro; la firma si disegna, si scrive o si carica come
immagine; poi **Valida e firma il documento**.

Lo stato si segue in **Firma → Richieste**: *Bozza*, *Inviata*, *Firmato*, *Annullata*. Ogni richiesta
ha il registro di creazione, visualizzazioni e firma (utente, partner, indirizzo IP, data) e
l'impronta (hash) del PDF firmato, che rende riconoscibile ogni modifica successiva.
Il **Certificato firma** si stampa dalla richiesta.

Un utente interno indicato come firmatario firma dal gestionale con **Firma adesso**.

## Firmare i preventivi (contratti)

Con le Vendite installate si aggiunge da solo il modulo `my_erp_crm_sale_sign`. Nel
preventivo c'è il pulsante **Invia alla firma**, che offre due scelte:

- **Il preventivo, con una pagina per le firme**: si firma il PDF del preventivo stesso. In
  fondo viene aggiunta una pagina "Accettazione del preventivo" con cliente, numero, data e
  totale, e gli spazi per *Nome e cognome* (si compila da solo), *Luogo e data* e *Firma*.
  Con **Firma anche la clinica** la pagina ha anche lo spazio per chi firma per la clinica
  (di solito tu).
- **Un modello di Firma**, per esempio il contratto in PDF. Il modello deve avere il campo
  *Modello* = **Ordine di vendita**, e il ruolo del cliente deve avere la politica
  *Espressione* con `{{object.partner_id.id}}`. Questa scelta compare solo se esiste
  almeno un modello così, e allora è proposta per prima.

Dopo **Invia**:
- il link per firmare arriva per email a chi firma;
- il preventivo passa a *Preventivo inviato*;
- nel registro del preventivo resta la nota con il link alla richiesta.

Chi firma per la clinica ed è un utente del gestionale riceve la richiesta anche nella posta
interna: può non avere l'email.

Il pulsante **Firme** del preventivo apre le richieste che lo riguardano. Quando tutti hanno
firmato, il **PDF firmato viene allegato al preventivo**, con la nota "Documento firmato
da …". Il preventivo **non** viene confermato da solo: lo confermi tu con **Conferma**.

## Cosa vale legalmente

È una **firma elettronica semplice**: identifica chi firma tramite il link personale inviato
alla sua email e conserva le prove (registro, IP, hash). Basta per molti consensi e
accettazioni, ma **non** è una firma elettronica qualificata (ZertES in Svizzera, eIDAS
nell'UE) né una firma avanzata con identificazione certificata. Per i documenti per cui la
legge chiede la forma scritta o la firma qualificata serve un servizio esterno certificato.
I documenti firmati restano sul server di my-erp-crm, con i backup del database.

## Note tecniche

Partenza: migrazione alla 20.0 proposta in OCA/sign
([PR 169](https://github.com/OCA/sign/pull/169), non ancora accettata), più le correzioni
OCA [PR 171](https://github.com/OCA/sign/pull/171) (il navigatore non chiede di validare
finché mancano campi obbligatori) e [PR 173](https://github.com/OCA/sign/pull/173) (tolto il
vecchio tour di test della versione 16). Modifiche di my-erp-crm:

- l'amministratore riceve il ruolo *Firma: Amministratore* all'installazione;
- nel PDF non si carica più uno script vuoto che andava in un ciclo di redirect;
- la copia firmata inviata per email si chiama `<nome del documento>.pdf` (prima `data`,
  senza estensione);
- nomi dei campi e dei ruoli traducibili; traduzione italiana completa per la 20.0;
- pagina dopo la firma: nella lingua di chi firma, promette l'email solo se l'invio della
  copia è attivo, e offre il link per scaricare il PDF firmato;
- nei test, un login che non va in conflitto con l'utente `portal` dei dati dimostrativi.

Test:

```bash
./my-erp-crm --addons-path=addons -d prova -i sign_oca --test-enable --test-tags /sign_oca --stop-after-init
```
