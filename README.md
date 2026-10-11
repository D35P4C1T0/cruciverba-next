# Cruciverba di laurea

Applicazione Flask mobile-first per raccogliere parole e indizi. Accesso invitati e pannello organizzatori separati, SQLite persistente, download PDF leggibile ed esportazione CSV.

## Configurazione

```bash
cp .env.example .env
openssl rand -hex 32
```

Incolla la chiave generata in `SECRET_KEY`, sostituisci le due password e configura `CELEBRATED_PERSON_NAME`.

## Pubblicazione con Traefik

In `.env` imposta `PUBLIC_HOSTNAME` al dominio pubblico. Il Compose di produzione contiene un solo servizio, chiamato `cruciverba`, collegato alla rete esterna `traefik`:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

La rete deve già esistere sul server ed essere condivisa con Traefik. Se ha un altro nome, imposta `TRAEFIK_NETWORK` in `.env`. Il container si chiama `cruciverba` e l'upstream è `http://cruciverba:5000`. Non servono porte pubblicate sull'host né label Traefik nel progetto.

La configurazione esistente di Traefik deve già gestire discovery/routing senza label e HTTPS per il dominio scelto: la sola rete offre connettività, mentre le rotte dipendono dalla configurazione del proxy. Con il provider Docker, questo può essere gestito da `exposedByDefault` e `defaultRule`; in alternativa usa il tuo provider file. Vedi la [documentazione Traefik](https://doc.traefik.io/traefik/v3.3/providers/docker/).

Il proxy deve impostare `X-Forwarded-For`, `X-Forwarded-Proto` e `X-Forwarded-Host`. `TRUSTED_PROXY_COUNT` vale `1` per un solo proxy; configura il numero esatto se la catena è diversa. L'app continua a richiedere HTTPS, dominio consentito e segreti validi in produzione.

## Avvio locale

```bash
docker compose up --build -d
```

Apri [http://localhost:5000](http://localhost:5000). `APP_PORT` e `BIND_ADDRESS` permettono di cambiare la porta e l'interfaccia locale. Questa configurazione non richiede Traefik.

Log, per entrambe le configurazioni:

```bash
docker logs -f cruciverba
```

## Rate limiting

Il default usa un worker Gunicorn con quattro thread e storage in memoria: nessun servizio aggiuntivo. Il limite generale è 120 richieste al minuto per IP e per endpoint. I login hanno anche un limite di 10 tentativi falliti al minuto per IP; login riusciti e contributi non consumano questa quota. Non ci sono più quote orarie o giornaliere. Cambia `RATE_LIMIT_DEFAULT` e `RATE_LIMIT_LOGIN` in `.env` per adattare i limiti.

Lo storage in memoria si azzera al riavvio. Gunicorn usa un solo worker per mantenere coerenti i contatori tra i thread e rifiuta configurazioni con più worker, anche tramite `GUNICORN_CMD_ARGS`. Per il traffico previsto basta un singolo container; non servono servizi aggiuntivi.

## Opzioni di deployment

- `CONTAINER_NAME` cambia il nome breve del container, utile per più installazioni sullo stesso server.
- `APP_IMAGE` seleziona un'immagine o un tag diverso. Per un'immagine già pubblicata usa `docker compose -f docker-compose.prod.yml up -d --no-build`.
- `DATABASE_PATH` cambia il percorso SQLite; mantienilo sotto `/app/data` per conservarlo nel volume.
- `GUNICORN_THREADS` cambia il numero di thread; `GUNICORN_CMD_ARGS` consente altre opzioni Gunicorn.

Non-root e healthcheck sono già nell'immagine. Per aggiungere filesystem read-only, capability rimosse e limiti di CPU, memoria e processi:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.hardened.yml up --build -d
```

Per un proxy eseguito sull'host usa il Compose locale e un override con le variabili di produzione, oppure aggiungi un mapping `ports` al Compose di produzione.

## Aggiornamento dalla configurazione precedente

Il volume `cruciverba_data` resta invariato. Mantieni lo stesso nome progetto Compose (directory o `-p`) per riutilizzare i dati. Prima di cambiare configurazione, ferma lo stack precedente con il suo file Compose, senza `-v`, poi avvia quello nuovo. Il servizio precedente `cruciverba-app` è sostituito da `cruciverba`.

Fai un backup del database prima degli aggiornamenti importanti. Se usi un altro nome progetto, monta esplicitamente il volume esistente; non creare per errore un volume vuoto.

## Password e segreti Docker

In produzione la chiave deve essere casuale e lunga almeno 32 caratteri; le password devono essere diverse dai valori predefiniti, senza placeholder e lunghe almeno 12 caratteri. `ALLOW_WEAK_PASSWORDS=True` permette consapevolmente password più corte, mantenendo le altre protezioni.

Supportati anche hash Werkzeug (`FORM_PASSWORD_HASH`, `ADMIN_PASSWORD_HASH`) e file di segreti:

```env
SECRET_KEY_FILE=/run/secrets/cruciverba_secret_key
FORM_PASSWORD_FILE=/run/secrets/cruciverba_form_password
ADMIN_PASSWORD_FILE=/run/secrets/cruciverba_admin_password
```

I file hanno precedenza sui valori diretti; gli hash hanno precedenza sulle password in chiaro. Monta i file tramite Docker secrets o bind mount.

## Download dei contributi

Nel pannello organizzatori, **Scarica PDF** crea un documento A4 pronto da leggere o stampare: parole numerate, indizi, autori e date, con pagine aggiunte automaticamente. **Esporta CSV** resta disponibile per lavorare con i dati in un foglio di calcolo. Entrambi i download richiedono l'accesso organizzatore.

Il PDF è generato in memoria: non richiede servizi aggiuntivi né file temporanei sul server.

## Protezioni applicative

CSRF sulle operazioni mutative, cookie `Secure`/`HttpOnly`/`SameSite=Lax`, sessioni di due ore, host allowlist, proxy trust esplicito e richieste limitate a 16 KiB. Restano CSP, anti-framing, HSTS su HTTPS, escaping Jinja, query SQLite parametrizzate e protezione CSV dalle formule. I log non contengono password o contenuti dei contributi.

## Test

Il build production esegue i test unitari prima di creare l'immagine finale:

```bash
docker build --target production -t cruciverba:local .
docker compose -p cruciverba-tests -f docker-compose.test.yml --profile test up --build --abort-on-container-exit
```


## Struttura del codice

- `app.py` e `wsgi.py`: avvio locale e produzione.
- `cruciverba/__init__.py`: factory `create_app`, configurazione e registrazione dei componenti.
- `cruciverba/config.py`: variabili d'ambiente, segreti e controlli di produzione.
- `cruciverba/contributions.py`: accesso invitati e invio contributi.
- `cruciverba/admin.py`: accesso organizzatori, elenco, eliminazione e download PDF/CSV.
- `cruciverba/exports.py`: impaginazione del PDF e nomi dei file esportati.
- `cruciverba/database.py`: connessioni SQLite, schema e query.
- `cruciverba/security.py`: verifica password, regole rate limiting, header e risposte di errore.
- `cruciverba/forms.py` e `validation.py`: validazione dei form e pulizia dell'input.

`create_app({...})` permette di creare app indipendenti con impostazioni specifiche per i test. Il percorso SQLite è in `app.config["DATABASE_PATH"]`; le funzioni database operano nel contesto dell'app attiva.
