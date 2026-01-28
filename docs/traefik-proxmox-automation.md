# Traefik Proxmox Automation

Système automatisé de découverte de containers Docker avec labels Traefik et mise à jour des notes Proxmox pour synchronisation avec un Traefik Gateway.

## Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Architecture](#architecture)
- [Intégration avec Traefik Proxmox Provider](#intégration-avec-traefik-proxmox-provider)
- [Modes de fonctionnement](#modes-de-fonctionnement)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Exemples](#exemples)
- [Dépannage](#dépannage)
- [Tests](#tests)

## Vue d'ensemble

Ce système permet de :

1. **Découvrir** automatiquement les containers Docker avec labels Traefik sur des VMs Proxmox
2. **Parser** et filtrer les labels Traefik selon le mode choisi
3. **Générer** des labels compatibles pour un Traefik Gateway
4. **Mettre à jour** automatiquement les notes Proxmox via l'API

### Cas d'usage principal

Synchroniser un **Traefik Gateway** (exposé sur Internet) avec des **Traefik locaux** tournant sur des VMs Proxmox, sans exposer directement les VMs.

Le système s'intègre parfaitement avec [**Traefik Proxmox Provider**](https://github.com/NX211/traefik-proxmox-provider) qui lit automatiquement les notes Proxmox et configure Traefik en temps réel.

## Architecture

### Architecture Pass-through (recommandée)

```
Internet
    ↓
┌──────────────────────────────────────────────┐
│   Traefik Gateway (VPS/Cloud)                │
│   - Port 443 (HTTPS/TLS)                     │
│   - Utilise Proxmox Provider                 │
│   - Lit les notes Proxmox via API            │
│   - Configure routes automatiquement         │
└──────────────────┬───────────────────────────┘
                   │ Polling (30s par défaut)
                   ↓
         ┌─────────────────────┐
         │  Proxmox API        │
         │  - Notes VM 106     │
         │  - Labels Traefik   │
         └──────────┬──────────┘
                    ↑
                    │ Mise à jour via Ansible
                    │
         ┌──────────┴──────────┐
         │   Ansible Playbook  │
         │   - Découvre labels │
         │   - Mode passthrough│
         │   - Update notes    │
         └──────────┬──────────┘
                    │ SSH
                    ↓
         ┌─────────────────────┐
         │  VM Proxmox (106)   │
         │  Traefik Local:8080 │
         └──────────┬──────────┘
                    │
         ┌──────────┴──────────┐
         ↓                     ↓
    Container A           Container B
    (miniflux)            (homarr)
```

### Flux de travail complet

```
1. Containers Docker avec labels Traefik
   ↓
2. Ansible se connecte à la VM Proxmox via SSH
   ↓
3. Execute inspect-docker.sh (liste les containers + labels)
   ↓
4. Parse les labels Traefik avec parse_docker_labels.py
   ↓
5. Génère les labels Gateway (mode filter ou passthrough)
   ↓
6. Met à jour les notes Proxmox via API
   ↓
7. Traefik Proxmox Provider détecte le changement (polling)
   ↓
8. Provider lit les notes et configure les routes
   ↓
9. Gateway Traefik route le trafic vers Traefik Local
   ↓
10. Traefik Local route vers les containers
```

## Modes de fonctionnement

### Mode Filter

Garde uniquement les labels essentiels pour le Gateway :

- ✅ `traefik.enable`
- ✅ `traefik.http.routers.*.rule`
- ✅ `traefik.http.routers.*.entrypoints`
- ✅ `traefik.http.routers.*.tls*`
- ✅ `traefik.http.services.*.loadbalancer.server.port`
- ❌ Labels Docker (`traefik.docker.*`)
- ❌ Middlewares (définitions et références)
- ❌ Labels TCP/UDP

**Réduction** : ~54% (26 labels → 12 labels)

### Mode Pass-through (recommandé)

Génère des labels Gateway qui :

1. **Copient exactement les routing rules** des containers locaux
2. **Pointent tous vers un seul service** (le Traefik local)
3. **Ajoutent TLS automatiquement** (Let's Encrypt)
4. **Simplifient les noms** (enlève le préfixe `mash-`)

**Exemple** :

```yaml
# Container local : mash-miniflux
traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)

# Devient sur le Gateway : miniflux
traefik.http.routers.miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)
traefik.http.routers.miniflux.service=homelab-traefik
traefik.http.routers.miniflux.entrypoints=websecure
traefik.http.routers.miniflux.tls=true
traefik.http.routers.miniflux.tls.certresolver=letsencrypt
```

**Réduction** : ~50% (26 labels → 13 labels : 2 routers + 1 service)

## Intégration avec Traefik Proxmox Provider

Ce système est conçu pour fonctionner parfaitement avec [**Traefik Proxmox Provider**](https://github.com/NX211/traefik-proxmox-provider), un provider Traefik qui lit automatiquement les notes des VMs Proxmox et génère la configuration Traefik dynamiquement.

### Pourquoi utiliser le Proxmox Provider ?

**Avantages** :
- ✅ **Configuration automatique** : Pas besoin de fichiers de config manuels
- ✅ **Détection en temps réel** : Polling toutes les 30 secondes par défaut
- ✅ **Source unique de vérité** : Les notes Proxmox comme configuration centrale
- ✅ **Pas de redémarrage** : Traefik se reconfigure automatiquement
- ✅ **Multi-VMs** : Gère plusieurs VMs automatiquement

### Architecture complète avec Provider

```
┌────────────────────────────────────────────────────────┐
│                    Internet                            │
└────────────────────────┬───────────────────────────────┘
                         ↓
         ┌───────────────────────────────┐
         │  Traefik Gateway (VPS/Cloud)  │
         │  ┌─────────────────────────┐  │
         │  │ Proxmox Provider Plugin │  │
         │  │ - Poll toutes les 30s   │  │
         │  │ - Lit notes Proxmox     │  │
         │  └─────────────────────────┘  │
         └───────────────┬───────────────┘
                         │ API HTTPS
                         ↓
         ┌───────────────────────────────┐
         │      Proxmox VE Server        │
         │  ┌─────────────────────────┐  │
         │  │ VM 106 (HomeLab)        │  │
         │  │ Notes: [Labels Traefik] │←─┼─── Ansible update
         │  └─────────────────────────┘  │
         └───────────────┬───────────────┘
                         │ Réseau local
                         ↓
         ┌───────────────────────────────┐
         │  VM 106 - Traefik Local:8080  │
         │  ┌──────────┐  ┌──────────┐   │
         │  │Container1│  │Container2│   │
         │  └──────────┘  └──────────┘   │
         └───────────────────────────────┘
```

### Installation du Proxmox Provider sur le Gateway

#### 1. Créer un fichier de configuration Traefik

Sur votre Traefik Gateway, créer `/etc/traefik/dynamic/proxmox-provider.yml` :

```yaml
providers:
  proxmox:
    # Endpoint Proxmox
    endpoint: "https://192.168.1.113:8006/api2/json"

    # Authentification
    username: "root@pam"
    token_name: "ansible"
    token_value: "VOTRE-TOKEN-SECRET"

    # Configuration
    insecure_skip_verify: true  # Si certificat auto-signé
    poll_interval: "30s"        # Fréquence de vérification

    # Filtre par tag (optionnel)
    tag: "exposed"              # Ne synchronise que les VMs avec ce tag
```

#### 2. Configuration Traefik statique

Dans `/etc/traefik/traefik.yml` :

```yaml
# Configuration statique
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https

  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt

# Certificate resolver
certificatesResolvers:
  letsencrypt:
    acme:
      email: votre.email@example.com
      storage: /etc/traefik/acme.json
      httpChallenge:
        entryPoint: web

# Providers
providers:
  # File provider pour config locale
  file:
    directory: /etc/traefik/dynamic
    watch: true

  # Proxmox Provider sera chargé via le plugin
  plugin:
    proxmox:
      moduleName: "github.com/NX211/traefik-proxmox-provider"
      version: "v0.2.0"
```

#### 3. Installation avec Docker Compose

```yaml
version: '3'

services:
  traefik:
    image: traefik:latest
    container_name: traefik-gateway
    restart: unless-stopped

    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Dashboard (optionnel)

    environment:
      # Variables pour le Proxmox Provider
      - PROXMOX_ENDPOINT=https://192.168.1.113:8006/api2/json
      - PROXMOX_USERNAME=root@pam
      - PROXMOX_TOKEN_NAME=ansible
      - PROXMOX_TOKEN_VALUE=votre-token-secret
      - PROXMOX_INSECURE_SKIP_VERIFY=true
      - PROXMOX_POLL_INTERVAL=30s

    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - ./dynamic:/etc/traefik/dynamic:ro
      - ./acme.json:/etc/traefik/acme.json

    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--experimental.plugins.proxmox.modulename=github.com/NX211/traefik-proxmox-provider"
      - "--experimental.plugins.proxmox.version=v0.2.0"
```

### Workflow complet avec Provider

1. **Développeur** : Ajoute des labels Traefik sur containers Docker
2. **Ansible** : Découvre les labels et met à jour les notes Proxmox
3. **Proxmox Provider** : Détecte le changement (polling 30s)
4. **Traefik Gateway** : Se reconfigure automatiquement
5. **Utilisateur final** : Accède au service via Internet

### Permissions requises pour le token Proxmox

Le token doit avoir ces permissions :

```bash
# Via pveum
pveum role add TraefikReader -privs "VM.Audit Sys.Audit"
pveum user token add root@pam ansible -privsep 1
pveum acl modify / -user root@pam -role TraefikReader
```

**Permissions minimales** :
- `VM.Audit` : Lire la configuration des VMs (incluant les notes)
- `Sys.Audit` : Lire les informations système

### Test de l'intégration

```bash
# 1. Lancer le playbook Ansible
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml

# 2. Vérifier les notes Proxmox
ansible-playbook playbooks/check-notes.yml -i inventory/my.proxmox.yml

# 3. Vérifier les logs du Proxmox Provider
docker logs traefik-gateway | grep proxmox

# 4. Tester l'accès
curl -I https://homelab.cy-bert.fr/miniflux
```

### Dépannage du Provider

#### Provider ne détecte pas les changements

```bash
# Vérifier la connectivité Proxmox API
curl -k https://192.168.1.113:8006/api2/json/version

# Vérifier l'authentification
curl -k \
  -H "Authorization: PVEAPIToken=root@pam!ansible=TOKEN" \
  https://192.168.1.113:8006/api2/json/nodes/pve/qemu/106/config
```

#### Provider génère des erreurs

```bash
# Augmenter le poll_interval si trop de requêtes
poll_interval: "60s"

# Vérifier les permissions du token
pveum user token permissions root@pam ansible
```

#### Configuration non appliquée

```bash
# Forcer un reload Traefik
docker restart traefik-gateway

# Vérifier la syntaxe des labels dans les notes
ansible-playbook playbooks/check-notes.yml -i inventory/my.proxmox.yml
```

### Avantages de cette architecture

✅ **Découplage** : Le Gateway ne se connecte qu'à Proxmox API, pas aux VMs
✅ **Sécurité** : Pas besoin d'exposer les VMs sur Internet
✅ **Automatisation** : Changement détecté en ~30 secondes
✅ **Centralisation** : Une seule source de vérité (notes Proxmox)
✅ **Évolutivité** : Fonctionne avec des dizaines de VMs
✅ **Traçabilité** : Historique des changements dans Proxmox

## Installation

### Prérequis

- Ansible installé (via Docker ou natif)
- Accès SSH aux VMs Proxmox
- API Token Proxmox avec droits VM.Audit et VM.Config
- Inventaire Proxmox dynamique configuré

### Fichiers installés

```
mash-playbook/
├── roles/
│   └── docker_traefik_discovery/       # Rôle Ansible
│       ├── tasks/main.yml              # Tâches principales
│       ├── library/
│       │   └── parse_docker_labels.py  # Module custom Python
│       └── files/
│           └── inspect-docker.sh       # Script d'inspection Docker
├── playbooks/
│   ├── discover-and-update.yml         # Playbook principal
│   └── check-notes.yml                 # Utilitaire de vérification
├── tests/
│   └── test_label_parsing.py           # Tests unitaires (31 tests)
├── inventory/
│   └── my.proxmox.yml                  # Inventaire dynamique Proxmox
└── .vault_pass.txt                     # Mot de passe Ansible Vault
```

## Configuration

### 1. Inventaire Proxmox

Fichier `inventory/my.proxmox.yml` :

```yaml
plugin: "community.proxmox.proxmox"
url: "https://192.168.1.113:8006"
user: "root@pam"
token_id: "ansible"
token_secret: "votre-token-ici"
validate_certs: false

want_facts: true

keyed_groups:
  - key: "proxmox_tags_parsed"
    prefix: ""
    separator: ""

compose:
  ansible_host: "'192.168.1.' ~ proxmox_vmid|string"
  ansible_user: ansible
  ansible_become: true
  ansible_become_method: sudo
  proxmox_node: proxmox_node
  proxmox_vmid: proxmox_vmid
```

### 2. Configuration du playbook

Fichier `playbooks/discover-and-update.yml` :

```yaml
vars:
  proxmox_api_host: "192.168.1.113"
  proxmox_api_user: "root@pam"
  proxmox_api_token_id: "ansible"
  proxmox_api_token_secret: "votre-token-ici"

  # Configuration Gateway
  gateway_mode: "passthrough"           # Options: 'filter' ou 'passthrough'
  traefik_local_port: 8080              # Port du Traefik local
  gateway_service_name: "homelab-traefik"  # Nom du service Gateway
```

### 3. Tags Proxmox

Les VMs doivent avoir le tag `exposed` pour être traitées :

```bash
# Via l'interface Proxmox ou l'API
pvesh set /nodes/{node}/qemu/{vmid}/config -tags exposed
```

## Utilisation

### Exécution du playbook

```bash
# Via l'alias Docker
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml

# Ou directement avec Docker (sans TTY pour scripts)
docker run --rm \
  -w /work \
  --mount type=bind,src=/opt/mash/mash-playbook,dst=/work \
  --mount type=bind,src=$HOME/.ssh,dst=/root/.ssh,ro \
  ansible-proxmox:latest \
  ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml
```

### Vérifier les notes Proxmox

```bash
ansible-playbook playbooks/check-notes.yml -i inventory/my.proxmox.yml
```

### Changer de mode

Éditer `playbooks/discover-and-update.yml` :

```yaml
# Pour le mode filter
gateway_mode: "filter"

# Pour le mode pass-through
gateway_mode: "passthrough"
```

## Exemples

### Exemple 1 : Mode Pass-through avec 2 containers

**Containers découverts :**
- `mash-miniflux` : 14 labels
- `mash-homarr` : 12 labels
- **Total : 26 labels**

**Labels générés pour le Gateway :**

```ini
traefik.enable=true

# Router 1 : homarr
traefik.http.routers.homarr.entrypoints=websecure
traefik.http.routers.homarr.rule=Host(`homelab.cy-bert.fr`)
traefik.http.routers.homarr.service=homelab-traefik
traefik.http.routers.homarr.tls=true
traefik.http.routers.homarr.tls.certresolver=letsencrypt

# Router 2 : miniflux
traefik.http.routers.miniflux.entrypoints=websecure
traefik.http.routers.miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)
traefik.http.routers.miniflux.service=homelab-traefik
traefik.http.routers.miniflux.tls=true
traefik.http.routers.miniflux.tls.certresolver=letsencrypt

# Service unique → Traefik local
traefik.http.services.homelab-traefik.loadbalancer.server.port=8080
traefik.http.services.homelab-traefik.loadbalancer.server.scheme=http
```

**Résultat : 13 labels** (2 routers × 5 labels + 1 service × 2 labels + 1 enable)

### Exemple 2 : Sortie du playbook

```
PLAY [Discover Docker containers and update Proxmox notes] *******************

TASK [Display execution info] *************************************************
ok: [HomeLab] => {
    "msg": "Starting Traefik labels discovery on HomeLab (VMID 106)"
}

TASK [docker_traefik_discovery : Check if Docker is installed] ***************
ok: [HomeLab]

TASK [docker_traefik_discovery : Execute Docker inspection script] ***********
ok: [HomeLab]

TASK [docker_traefik_discovery : Display discovered labels count] ************
ok: [HomeLab] => {
    "msg": "Found 26 Traefik labels across 2 containers"
}

TASK [docker_traefik_discovery : Parse and format labels for Proxmox] ********
changed: [HomeLab]

TASK [docker_traefik_discovery : Display formatted labels summary] ***********
ok: [HomeLab] => {
    "msg": "Parsed 13 labels (2 routers, 1 services, 0 middlewares)"
}

TASK [docker_traefik_discovery : Update Proxmox notes via API] ***************
ok: [HomeLab]

TASK [docker_traefik_discovery : Display success message] ********************
ok: [HomeLab] => {
    "msg": "Updated Proxmox notes for HomeLab (VMID 106) with 13 Traefik labels"
}

PLAY RECAP ********************************************************************
HomeLab                    : ok=15   changed=3    unreachable=0    failed=0
```

## Dépannage

### Erreur : "the role 'docker_traefik_discovery' was not found"

**Cause** : Le chemin des rôles n'est pas configuré correctement.

**Solution** : Vérifier `ansible.cfg` :

```ini
[defaults]
roles_path = roles
```

### Erreur : "Permission denied (Docker)"

**Cause** : L'utilisateur Ansible ne peut pas accéder au socket Docker.

**Solution** : Le script `inspect-docker.sh` détecte automatiquement si `sudo` est nécessaire. Vérifier que l'utilisateur a les droits sudo sans mot de passe pour Docker :

```bash
# Sur la VM Proxmox
sudo visudo
# Ajouter :
ansible ALL=(ALL) NOPASSWD: /usr/bin/docker
```

### Erreur : "the input device is not a TTY"

**Cause** : L'alias `ansible-playbook` dans `.bashrc` utilise `docker run -it`.

**Solution** : Pour les scripts non-interactifs, utiliser la commande Docker complète sans `-it` :

```bash
docker run --rm -w /work \
  --mount type=bind,src=/opt/mash/mash-playbook,dst=/work \
  --mount type=bind,src=$HOME/.ssh,dst=/root/.ssh,ro \
  ansible-proxmox:latest \
  ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml
```

### Erreur : "0 Traefik labels found"

**Causes possibles** :
1. Les containers n'ont pas de labels Traefik
2. L'extraction JSON échoue

**Solution** : Exécuter avec verbosité :

```bash
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml -vvv
```

### Vérifier les notes Proxmox manuellement

```bash
# Via l'API directement
curl -s -k \
  -H 'Authorization: PVEAPIToken=root@pam!ansible=VOTRE-TOKEN' \
  'https://192.168.1.113:8006/api2/json/nodes/NODENAME/qemu/106/config' \
  | python3 -m json.tool | grep description

# Ou via le playbook utilitaire
ansible-playbook playbooks/check-notes.yml -i inventory/my.proxmox.yml
```

## Tests

### Exécuter les tests unitaires

```bash
cd /opt/mash/mash-playbook/tests
python3 test_label_parsing.py
```

### Résultats attendus

```
Ran 31 tests in 0.002s

OK
```

### Catégories de tests

- **Tests de parsing** (8 tests) : Vérification du parsing des labels Traefik
- **Tests de filtrage** (9 tests) : Vérification du mode filter
- **Tests pass-through** (7 tests) : Vérification du mode pass-through
- **Tests de formatage** (7 tests) : Vérification de la génération Proxmox

### Exécuter un test spécifique

```bash
python3 test_label_parsing.py TestGatewayPassthrough.test_passthrough_single_router
```

## Sécurité

### Bonnes pratiques

1. **API Token Proxmox** : Utiliser un token dédié avec droits minimaux
   - `VM.Audit` : Lecture des configurations
   - `VM.Config.Options` : Modification des notes

2. **Vault Password** : Protéger `.vault_pass.txt`
   ```bash
   chmod 600 .vault_pass.txt
   ```

3. **SSH Keys** : Utiliser des clés SSH dédiées pour Ansible
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/ansible_proxmox
   ```

4. **Pas de secrets dans les notes** : Les notes Proxmox sont visibles, ne pas y mettre de secrets

## Performance

- **Temps d'exécution moyen** : ~15-20 secondes pour 2 containers
- **Scaling** : Linéaire avec le nombre de VMs et containers
- **Cache** : Aucun cache, exécution complète à chaque run

## Limitations

1. **Supporte uniquement Docker** : Pas de support Podman/autres runtimes
2. **Routers HTTP uniquement** : Pas de support TCP/UDP dans les modes filter/passthrough
3. **Single-node** : Pas de support multi-node Proxmox cluster pour le moment
4. **Labels statiques** : Les changements de labels nécessitent une nouvelle exécution

## Roadmap

- [ ] Support multi-nodes Proxmox
- [ ] Mode watch pour détection automatique des changements
- [ ] Support des routers TCP
- [ ] Intégration avec Traefik File Provider
- [ ] Dashboard de visualisation

## Références

- [Documentation Traefik](https://doc.traefik.io/traefik/)
- [API Proxmox](https://pve.proxmox.com/pve-docs/api-viewer/)
- [Ansible Dynamic Inventory - Proxmox](https://docs.ansible.com/ansible/latest/collections/community/proxmox/proxmox_inventory.html)

## Auteur

Généré avec [Claude Code](https://claude.com/claude-code)

## License

Même license que mash-playbook (AGPL-3.0)
