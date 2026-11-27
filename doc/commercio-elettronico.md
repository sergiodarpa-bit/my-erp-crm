# Commercio elettronico

Il negozio online di my-erp-crm è l'app **Sito web → E-commerce**: catalogo, carrello,
pagamento, conferma d'ordine, fattura. Risponde all'indirizzo del gestionale seguito da
`/shop` (per esempio https://erp.kliniksanktmoritz.ch/shop): la radice `/` apre il gestionale,
`/shop` il negozio.

Il modulo `my_erp_crm_shop` aggiunge gli strumenti per aprirlo con le regole IVA di
my-erp-crm. Si installa da solo dove il negozio c'è già, al primo aggiornamento:

| Strumento | Che cosa fa |
|---|---|
| **Controllo di lancio** | Sito web → Configurazione → E-commerce → **Controllo di lancio**: l'elenco di che cosa è pronto e che cosa manca, con dove si sistema |
| **IVA prima del pagamento** | un carrello che non si potrebbe fatturare non arriva al pagamento: il cliente lo sa prima di pagare, non dopo |
| **Pagamento mai perso** | se una fattura automatica non si può emettere, il pagamento è registrato, l'ordine confermato, la fattura resta in bozza con un'attività |
| **Panoramica** | i carrelli del sito non contano più fra i «preventivi da confermare»; la tessera **Sito web** mostra gli **ordini online da gestire** |
| **Dashboard** | il cruscotto **E-commerce** dell'app Dashboard è sempre installato |

All'installazione il modulo imposta, una volta sola (poi si cambia dalle Impostazioni):

- il listino pubblico in euro disponibile sul negozio (senza, il negozio mostrerebbe i prezzi
  interni in sterline);
- la **fattura automatica**: ordine pagato online, fattura emessa e inviata da sola;
- il paese del cliente sempre richiesto, anche per i soli servizi;
- le vendite online nell'email di riepilogo.

I metodi di pagamento restano **spenti**: il lancio lo decide chi gestisce il negozio.

## Aprire il negozio, passo per passo

Si apre **Sito web → Configurazione → E-commerce → Controllo di lancio** e si sistemano le voci
in rosso («Manca»), dall'alto. «Ricontrolla» rifà l'elenco. Le voci in giallo («Da sapere»)
non bloccano il lancio, ma vanno sapute.

### 1. La posta in uscita

Senza, il cliente non riceve né la conferma d'ordine né la fattura, e nessuno se ne accorge.
Si configura e si prova come in [posta-in-uscita.md](posta-in-uscita.md).

### 2. Prodotti e prezzi

- I prezzi pubblici sono nel listino **Public prices (EUR)** (Vendite → Prodotti → Listini
  prezzi): per ogni prodotto una regola «prezzo fisso» in euro. Senza regola il negozio
  converte il prezzo di vendita in sterline, quasi sempre a zero.
- Ogni prodotto in vendita: nome e descrizione per il cliente, immagine, imposta giusta
  (**No UK VAT** per i servizi generali come il check-up, **No UK VAT - digital** per i
  servizi digitali come l'abbonamento all'app), poi «Vai al sito web» → **Pubblicato**.
- La consulenza su misura non ha listino: non si pubblica, si vende con un preventivo.

Il controllo di lancio elenca i prodotti pubblicati **senza prezzo**: si venderebbero a zero.

### 3. I pagamenti

**Sito web → Configurazione → E-commerce → Pagamenti.**

**Stripe** (carte di tutto il mondo; Apple Pay e Google Pay con qualche impostazione in più):

1. Dal proprio conto Stripe (dashboard.stripe.com → Sviluppatori → Chiavi API) si copiano la
   **chiave pubblicabile** e la **chiave privata**. Si incollano nei campi «Chiave
   pubblicabile» e «Chiave privata» del metodo Stripe. Non si usa il pulsante **«Connetti»**:
   apre il conto attraverso la piattaforma di Odoo S.A. (stripe.api.odoo.com), mentre
   my-erp-crm parla direttamente con i servizi che usa.
2. **«Genera il tuo webhook»**: Stripe avvisa il gestionale di ogni pagamento, anche se il
   cliente chiude la pagina prima di tornare al negozio.
3. Prima le chiavi **di prova** (`pk_test_…`, `sk_test_…`) con «Attivo» spento: si paga con la
   carta di prova `4242 4242 4242 4242`, una scadenza futura qualsiasi, un CVC qualsiasi.

**Bonifico** (per chi preferisce, o per importi alti): metodo «Bonifico bancario», conto bancario
dell'azienda (quello di `COMPANY_IBAN`). L'ordine resta «in attesa di pagamento» finché il
bonifico non arriva: lo si conferma dalla contabilità, e nel frattempo compare fra gli ordini
online da gestire della Panoramica.

Le chiavi si scrivono solo nei campi del gestionale: mai in `.env`, in documenti o messaggi.

### 4. Termini e condizioni

**Contabilità → Configurazione → Impostazioni → «Condizioni Generali»** → «Come pagina web»:
il testo delle condizioni di vendita (servizi, recesso, rimborsi, legge applicabile), scritto
con chi segue gli aspetti legali. Diventa la pagina `/terms`. Poi nel negozio, alla pagina di
pagamento, «Modifica» → accendere **«Accetta termini e condizioni»**: il cliente deve
spuntarla per pagare.

### 5. Prova d'acquisto

Con Stripe in prova si compra davvero dal negozio, da una finestra anonima:

| Cliente di prova | Prodotto | Che cosa deve succedere |
|---|---|---|
| privato italiano | check-up | pagamento, email di conferma, fattura emessa e inviata con la dicitura «fuori campo VAT britannica» |
| privato italiano | abbonamento app | **il pagamento non si apre**: messaggio «non si possono ancora vendere online ai privati del tuo paese» (manca l'OSS, vedi sotto) |
| impresa tedesca con partita IVA valida | abbonamento app | pagamento, fattura in reverse charge |
| privato svizzero | check-up | pagamento, fattura «fuori campo» |

Poi si guarda che l'ordine sia nella Panoramica e nei cruscotti (sotto), e che la fattura sia
nella contabilità con il pagamento abbinato.

### 6. Lancio

Chiavi **di produzione** (`pk_live_…`, `sk_live_…`), di nuovo «Genera il tuo webhook», poi
**«Attivo»** e **«Pubblicato»**. Il controllo di lancio senza voci rosse dice «Pronto per
aprire».

## L'IVA nel negozio

Il negozio usa le stesse regole della contabilità ([README](../README.md#azienda-iva-e-prezzi)),
ma prima del pagamento, invece che alla fattura:

| Cliente | Al checkout |
|---|---|
| Regno Unito, Svizzera, resto del mondo | si paga; fattura senza VAT con la sua dicitura |
| impresa UE con partita IVA **verificata VIES** | si paga; reverse charge. La verifica parte quando il cliente scrive la partita IVA nell'indirizzo di fatturazione, anche se la aggiunge dopo |
| privato UE (o impresa UE senza VIES valido) | servizi generali: si paga, fuori campo. **Servizi digitali: il pagamento non si apre** finché non c'è la registrazione OSS non-UE |
| prodotto senza imposta, cliente senza posizione fiscale | il pagamento non si apre: va prima messa l'imposta al prodotto |

Il controllo vale anche sul server: non basta saltare la pagina di pagamento per creare una
transazione.

**Con la registrazione OSS** (`OSS_REGISTERED=1`, vedi il README) i servizi digitali ai
privati UE si vendono con l'IVA del loro paese e servono **due prove** del paese del cliente.
Il negozio le raccoglie da solo al pagamento: il paese dell'indirizzo di fatturazione e quello
della connessione (dall'indirizzo IP, che non viene conservato). Le prove passano nella fattura.
Se i due paesi non coincidono, o il paese della connessione non si conosce, il pagamento non
si apre e il cliente è invitato a contattarci. Il paese della connessione richiede sul server
il database GeoIP gratuito di MaxMind (`GeoLite2-Country.mmdb` in `/usr/share/GeoIP/`, oppure
l'opzione `geoip_country_db`): finché manca, il controllo di lancio lo segnala.

## Quando una fattura non si può emettere

Può succedere con un preventivo pagato dal portale, o se l'imposta di un prodotto cambia a
ordine aperto. Il pagamento non si perde:

- l'ordine è confermato e il pagamento registrato (come acconto del cliente);
- la fattura resta **in bozza**, con un'**attività «Fattura da completare (IVA)»** per il
  venditore dell'ordine, e il motivo è scritto anche sull'ordine;
- si sistema il trattamento IVA (posizione fiscale, imposta, prove OSS), si conferma la fattura
  e la si abbina al pagamento, che la contabilità propone fra i crediti del cliente.

L'ordine compare fra gli **ordini online da gestire** della Panoramica finché la fattura non è
emessa.

## Dove si vedono i numeri

| Dove | Che cosa |
|---|---|
| **Panoramica** (prima pagina dopo l'accesso) | tessera Sito web: **ordini online da gestire** (bonifici attesi, fatture da emettere); tessera Vendite: preventivi da confermare, senza i carrelli; tessera Contabilità: fatture da incassare |
| **Dashboard → E-commerce** | incasso, ordini, carrelli e carrelli abbandonati, prodotti e categorie più venduti (per i responsabili vendite); accanto, i cruscotti **Vendite** e **Fatturazione** |
| **Sito web → Rendiconto → Vendite online** | analisi a tabella e grafico degli ordini del sito, per prodotto, paese, periodo |
| **Sito web → E-commerce → Ordini** | gli ordini uno per uno; **Carrelli abbandonati** (in modalità sviluppatore) per ricontattare chi non ha finito |
| **Contabilità** | gli incassi online nel registro del metodo di pagamento (campo «Registro» del metodo), le fatture del negozio |
| **Email di riepilogo** | le vendite e-commerce nel riepilogo periodico, con gli altri numeri |

I numeri dei cruscotti sono nella valuta contabile (sterline); i prezzi del negozio e le
fatture sono in euro.
