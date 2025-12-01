# 🌐 Cruciverba Nexus

Un'applicazione web sicura e general-purpose per raccogliere parole e frasi indizio dagli ospiti per creare cruciverba personalizzati. Il nome della persona celebrata è configurabile tramite variabili d'ambiente Docker.

## ✨ Funzionalità

- **Form protetto da password** per gli invitati  
- **Pannello amministratore** sicuro per visualizzare ed esportare i contributi
- **Eliminazione individuale** dei contributi non desiderati
- **Protezione anti-spam** con honeypot e validazione rigorosa
- **Design responsive** ottimizzato per dispositivi mobili
- **Dark/Light mode automatico** basato sul tema del dispositivo
- **Sicurezza enterprise-grade** per deployment pubblico
- **Esportazione CSV** completa dei contributi
- **37 test automatici** con CI/CD integrato
- **Dockerizzato** per deployment semplificato

## 🛡️ Sicurezza Avanzata

Questa applicazione include multiple misure di sicurezza per deployment pubblico:

- ✅ **Rate Limiting**: Protezione contro spam e brute force attacks
- ✅ **Protezione CSRF**: Token CSRF su tutti i form sensibili
- ✅ **Security Headers**: CSP, HSTS, X-Frame-Options per prevenire XSS e clickjacking
- ✅ **Input Sanitization**: Pulizia e validazione rigorosa di tutti gli input utente
- ✅ **Environment Variables**: Password e secrets gestiti tramite variabili d'ambiente
- ✅ **Logging di sicurezza**: Tracciamento completo degli eventi di sicurezza
- ✅ **Session Security**: Cookie sicuri con attributi httpOnly e secure
- ✅ **Database Security**: Query parametrizzate e WAL mode
- ✅ **Container Security**: Non-root user, minimal surface, security constraints

## 🚀 Installazione e Avvio

### Prerequisiti
- Docker e Docker Compose installati sul sistema
- Almeno 1GB di spazio libero per i container

### Setup Completo

1. **Clona il repository**:
   ```bash
   git clone <repository-url>
   cd cruciverba-nexus
   ```

2. **Configura le password di sicurezza**:
   ```bash
   # Copia il template di configurazione
   cp .env.example .env
   
   # Genera password sicure
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
   python3 -c "import secrets; print('FORM_PASSWORD=' + secrets.token_urlsafe(16))"
   python3 -c "import secrets; print('ADMIN_PASSWORD=' + secrets.token_urlsafe(16))"
   ```

3. **Modifica `.env` con le password generate** (IMPORTANTE):
   ```bash
   nano .env
   ```
   
   **Esempio configurazione sicura**:
   ```env
   SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
   FORM_PASSWORD=InvitatiPassword2025
   ADMIN_PASSWORD=AdminPassword2025Secure
   CELEBRATED_PERSON_NAME=Bianca
   FLASK_ENV=production
   DEBUG=False
   ```

4. **Avvia l'applicazione**:
   ```bash
   # Build e start con test automatici
   docker-compose up -d
   
   # Verifica che sia attiva
   curl http://localhost:8080
   ```

### Avvio Rapido (Solo Test)

```bash
# Usa password di default (SOLO per test locali)
echo "FORM_PASSWORD=bianca" > .env
echo "ADMIN_PASSWORD=bianca2025" >> .env
echo "CELEBRATED_PERSON_NAME=Bianca" >> .env
echo "SECRET_KEY=test-secret-key-$(date +%s)" >> .env

docker-compose up -d
```

L'applicazione sarà disponibile su http://localhost:8080

## 🏗️ Architettura e Quality Gates

### Test Suite Completo
- **37 test automatici** con coverage completo
- **Security testing**: XSS, CSRF, rate limiting, input validation
- **Integration testing**: End-to-end user workflows
- **Docker build gates**: I test devono passare per il deployment

### Sicurezza Multi-Layer
```
🌐 Internet → 🛡️ Reverse Proxy → 🐳 Docker → 🔒 Flask App
                    (nginx/Apache)      (Container)   (Rate limits, CSRF, etc.)
```

### Database Design
- **SQLite con WAL mode** per performance e concorrenza
- **Query parametrizzate** per prevenire SQL injection
- **Backup automatici** e easy data migration

## 📱 Utilizzo

### Per gli Invitati
1. **Accesso**: Visita il sito e inserisci la password fornita
2. **Contributo**: Compila il form con:
   - **Parola/Frase**: Che ti ricorda la persona celebrata (lettere e spazi)
   - **Frase indizio**: Descrizione per indovinare (min 10 caratteri)
   - **Nome**: Opzionale, puoi rimanere anonimo
3. **Multi-contributi**: Dopo l'invio, puoi aggiungere altre parole
4. **Logout**: Usa "Finito, disconnetti" quando hai finito

### Per gli Amministratori
1. **Accesso**: Vai su `/admin` e inserisci la password admin
2. **Dashboard**: Visualizza tutti i contributi in ordine cronologico
3. **Export**: Scarica CSV completo per creare il cruciverba
4. **Gestione**: Elimina contributi inappropriati (individualmente)
5. **Monitoring**: Controlla i log di sicurezza

## 🔧 Configurazione Avanzata

### Variabili d'Ambiente (`.env`)

```bash
# === SICUREZZA (OBBLIGATORIO PER PRODUZIONE) ===
SECRET_KEY=your-super-secret-key-64-chars-minimum
FORM_PASSWORD=password-per-invitati-sicura
ADMIN_PASSWORD=password-admin-molto-sicura

# === PERSONA CELEBRATA ===
CELEBRATED_PERSON_NAME=Bianca

# === DATABASE ===
DATABASE_PATH=data/cruciverba.db

# === RATE LIMITING ===
RATE_LIMIT_STORAGE_URL=memory://

# === FLASK ENVIRONMENT ===
FLASK_ENV=production
DEBUG=False

# === HTTPS (per deployment pubblico) ===
FORCE_HTTPS=True
```

### Rate Limiting Configurato

| Endpoint | Limite | Scopo |
|----------|--------|--------|
| Form submissions | 30/min | Prevenire spam |
| Admin login | 20/min | Proteggere admin |
| CSV export | 10/min | Rate limit admin actions |
| General | 200/day | Protezione generale |

### Deployment Sicuro

#### Per Produzione:
```bash
# 1. Password robuste (NON usare quelle di default)
python3 -c "import secrets; print(secrets.token_hex(32))"

# 2. HTTPS obbligatorio
echo "FORCE_HTTPS=True" >> .env

# 3. Reverse proxy (nginx esempio)
server {
    listen 443 ssl;
    server_name cruciverba.tuodominio.it;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# 4. Monitoring continuo
docker-compose logs -f cruciverba-app | grep "SECURITY EVENT"
```

## 🧪 Testing e Quality Assurance

### Test Suite (37 test)
```bash
# Run tutti i test
./run_tests.sh all

# Solo test unitari (veloce)
./run_tests.sh unit  

# Test di integrazione (richiede app running)
./run_tests.sh integration

# Coverage report
./run_tests.sh coverage
```

### Test Categories
- **Security**: Headers, XSS prevention, CSRF, rate limiting
- **Authentication**: Login/logout, session management
- **Form Processing**: Validation, sanitization, duplicates
- **Admin Functions**: Dashboard, export, deletion
- **Database**: CRUD operations, integrity
- **Error Handling**: 404s, invalid inputs

### CI/CD Pipeline
- ✅ **Automated testing** su ogni commit
- ✅ **Security scanning** con Trivy
- ✅ **Multi-environment deployment** (staging → production)
- ✅ **Quality gates** obbligatori

## 📊 Monitoraggio e Manutenzione

### Log di Sicurezza
```bash
# Eventi di sicurezza in tempo reale
docker-compose logs -f cruciverba-app | grep "SECURITY EVENT"

# Esempi di eventi tracciati:
# - Tentativi di login falliti
# - Rate limiting attivato  
# - Errori CSRF
# - Input malicious bloccati
```

### Backup dei Dati
```bash
# Backup automatico
cp ./data/cruciverba.db ./backup_cruciverba_$(date +%Y%m%d_%H%M%S).db

# Backup programmatico
docker-compose exec cruciverba-app sqlite3 /app/data/cruciverba.db ".backup /app/data/backup_$(date +%Y%m%d).db"

# Restore da backup
docker-compose down
cp backup_cruciverba_YYYYMMDD_HHMMSS.db ./data/cruciverba.db
docker-compose up -d
```

### Health Checks
```bash
# Status applicazione
curl -I http://localhost:8080

# Health endpoint (se configurato)
curl http://localhost:8080/health

# Database connectivity
docker-compose exec cruciverba-app sqlite3 /app/data/cruciverba.db "SELECT COUNT(*) FROM submissions;"
```

## 🐛 Troubleshooting

### Problemi Comuni

#### 1. Password non funziona
```bash
# Verifica configurazione
cat .env | grep PASSWORD

# Restart per ricaricare environment
docker-compose restart

# Check logs per dettagli
docker-compose logs cruciverba-app | tail -20
```

#### 2. Rate limiting eccessivo
```bash
# Temporary disable (development only)
echo "RATE_LIMIT_STORAGE_URL=null://" >> .env
docker-compose restart

# Check rate limit storage
docker-compose exec cruciverba-app env | grep RATE_LIMIT
```

#### 3. Database locked/corrupted
```bash
# Check WAL files
ls -la data/cruciverba.db*

# Checkpoint WAL to main DB
docker-compose exec cruciverba-app sqlite3 /app/data/cruciverba.db "PRAGMA wal_checkpoint;"

# Verify integrity
docker-compose exec cruciverba-app sqlite3 /app/data/cruciverba.db "PRAGMA integrity_check;"
```

#### 4. Container won't start
```bash
# Full reset
docker-compose down
docker system prune -f
docker-compose build --no-cache
docker-compose up -d

# Check build logs
docker-compose logs --no-color cruciverba-app
```

### Errori di Sicurezza

| Errore | Significato | Azione |
|--------|-------------|--------|
| `INVALID_ADMIN_PASSWORD` | Tentativo login admin fallito | Controllare password, possibile attacco |
| `RATE_LIMIT_EXCEEDED` | Troppi tentativi | IP bloccato temporaneamente |
| `CSRF_ERROR` | Token CSRF invalido | Sessione scaduta o tentativo di attacco |
| `XSS_ATTEMPT_BLOCKED` | Input malicious rilevato | Input automaticamente sanificato |

## 📈 Performance e Scaling

### Ottimizzazioni Applicate
- **SQLite WAL mode** per concorrenza migliorata
- **Container non-root** per sicurezza
- **Static asset caching** con proper headers
- **Gzip compression** per risposte più veloci
- **Health checks** per monitoring

### Scaling Orizzontale (se necessario)
```yaml
# docker-compose.scale.yml
version: '3.8'
services:
  cruciverba-app:
    deploy:
      replicas: 3
    depends_on:
      - database
  
  database:
    image: postgres:15
    # Migrate da SQLite a PostgreSQL per maggiore concorrenza
```

## 🤝 Contributi e Supporto

### Per Sviluppatori
1. **Fork** il repository
2. **Crea** un branch feature: `git checkout -b feature/amazing-feature`
3. **Commit** le modifiche: `git commit -m 'Add amazing feature'`
4. **Push** al branch: `git push origin feature/amazing-feature`
5. **Apri** una Pull Request

### Quality Requirements
- ✅ Tutti i test devono passare
- ✅ Coverage > 90%
- ✅ Security scan pulito
- ✅ Documentation aggiornata

### Issues e Bug Reports
Usa il template di issue con:
- Versione Docker/OS
- Log di errore completi
- Passi per riprodurre
- Configurazione environment (senza password!)

---

## 📋 Quick Reference

### Comandi Essenziali
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs  
docker-compose logs -f cruciverba-app

# Test
./run_tests.sh all

# Backup
cp data/cruciverba.db backup_$(date +%Y%m%d).db

# Reset completo
docker-compose down && docker system prune -f && docker-compose up -d
```

### URLs Importanti
- **Applicazione**: http://localhost:8080
- **Admin Panel**: http://localhost:8080/admin
- **Logout**: http://localhost:8080/logout

### File Critici
- `.env` - Configurazione e password
- `data/cruciverba.db` - Database principale
- `docker-compose.yml` - Orchestrazione container
- `app.py` - Applicazione principale

---

🎓 **Cruciverba Nexus - Applicazione general-purpose per cruciverba personalizzati** 🎉

*Applicazione sviluppata con ❤️ per celebrare momenti speciali* 