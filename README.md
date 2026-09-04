# Cruciverba di laurea

Applicazione Flask mobile-first per raccogliere parole e indizi. Accesso invitati e pannello organizzatori separati, SQLite persistente, esportazione CSV.

## Avvio locale sulla porta 5000

```bash
cp .env.example .env
```

Sostituisci le password e genera una chiave di sessione:

```bash
openssl rand -hex 32
```

Incolla il risultato in `SECRET_KEY`, poi avvia:

```bash
docker compose up --build -d
```

Apri [http://localhost:5000](http://localhost:5000). Log:

```bash
docker compose logs -f cruciverba-app
```

## Pubblicazione homelab

Serve un reverse proxy HTTPS, per esempio Caddy, Traefik o Nginx. In `.env` configura:

```env
CELEBRATED_PERSON_NAME=Emily
PUBLIC_HOSTNAME=cruciverba.example.it
FORM_PASSWORD=una-password-invitati-lunga-e-unica
ADMIN_PASSWORD=una-password-admin-diversa-e-lunga
SECRET_KEY=64-caratteri-casuali-generati-con-openssl
ALLOW_WEAK_PASSWORDS=False
BIND_ADDRESS=127.0.0.1
APP_PORT=5000
TRUSTED_PROXY_COUNT=1
```

Avvia configurazione production:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

`BIND_ADDRESS=127.0.0.1` espone app solo al proxy eseguito sullo stesso host. Se proxy gira in un container, collegalo alla rete dedicata:

```bash
docker network connect cruciverba_frontend NOME_CONTAINER_PROXY
```

Poi usa `cruciverba-app:5000` come upstream. Non pubblicare direttamente porta applicativa su Internet.

Proxy deve terminare TLS e impostare `X-Forwarded-For`, `X-Forwarded-Proto` e `X-Forwarded-Host`. `TRUSTED_PROXY_COUNT` deve corrispondere al numero esatto di proxy fidati: normalmente `1`; Cloudflare più proxy locale richiedono verifica della catena prima di usare `2`.

Configurazione production rifiuta avvio quando:

- chiave sessione manca, è placeholder o è troppo corta;
- password sono predefinite, placeholder o più corte di 12 caratteri;
- HTTPS, host consentiti o rate limiter Redis non sono configurati.

Per accettare consapevolmente password corte, imposta in `.env`:

```env
ALLOW_WEAK_PASSWORDS=True
```

Questo disattiva solo il controllo di robustezza di `FORM_PASSWORD` e
`ADMIN_PASSWORD`. Tutte le altre protezioni restano obbligatorie. L'opzione è
sconsigliata per un servizio raggiungibile da Internet; il rate limiting riduce
i tentativi, ma non rende sicura una password debole.

Il nome del festeggiato resta configurabile tramite `CELEBRATED_PERSON_NAME`.

## Segreti Docker

App supporta convenzione `*_FILE`, utile con Docker secrets o bind mount protetti:

```env
SECRET_KEY_FILE=/run/secrets/cruciverba_secret_key
FORM_PASSWORD_FILE=/run/secrets/cruciverba_form_password
ADMIN_PASSWORD_FILE=/run/secrets/cruciverba_admin_password
```

Supportati anche `FORM_PASSWORD_HASH` e `ADMIN_PASSWORD_HASH` generati con Werkzeug. Hash ha precedenza sulla password in chiaro.

## Protezioni incluse

- Gunicorn, mai server Flask di sviluppo in production;
- container non-root, filesystem read-only, capability rimosse, limiti processi/memoria;
- Redis privato per rate limiting condiviso fra worker;
- CSRF su tutte le operazioni mutative, logout incluso;
- cookie `Secure`, `HttpOnly`, `SameSite=Lax` e sessioni di due ore;
- host allowlist, proxy trust esplicito, limite richieste 16 KiB;
- CSP, anti-framing, HSTS solo su HTTPS e no-cache per pagine private;
- query SQLite parametrizzate, timeout scritture, escaping Jinja e CSV formula protection;
- log senza password o contenuto dei contributi.

## Test

Build production esegue test unitari prima di creare immagine finale:

```bash
docker build --target production -t cruciverba-nexus-app:production .
```

Solo test:

```bash
docker compose -f docker-compose.test.yml --profile test up --build --abort-on-container-exit
```

Backup database prima degli aggiornamenti importanti. Dati vivono nel volume `cruciverba_data`.
