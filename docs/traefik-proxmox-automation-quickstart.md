# Traefik Proxmox Automation - Guide de démarrage rapide

Guide condensé pour démarrer rapidement avec le système de découverte Traefik-Proxmox.

Ce système fonctionne avec [**Traefik Proxmox Provider**](https://github.com/NX211/traefik-proxmox-provider) pour une configuration automatique du Gateway Traefik.

## Installation en 5 minutes

### 1. Créer un API Token Proxmox

```bash
# Via l'interface web Proxmox :
# Datacenter → Permissions → API Tokens → Add

# Ou via CLI :
pveum user token add root@pam ansible -privsep 0
```

Copier le token généré (format : `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### 2. Configurer l'inventaire

Éditer `inventory/my.proxmox.yml` :

```yaml
plugin: "community.proxmox.proxmox"
url: "https://IP-PROXMOX:8006"
user: "root@pam"
token_id: "ansible"
token_secret: "VOTRE-TOKEN-ICI"
validate_certs: false
```

### 3. Taguer vos VMs

Ajouter le tag `exposed` aux VMs à découvrir :

```bash
# Via pvesh
pvesh set /nodes/NODENAME/qemu/VMID/config -tags exposed

# Ou via l'interface web Proxmox
```

### 4. Lancer la découverte

```bash
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml
```

### 5. Installer Traefik Proxmox Provider sur le Gateway

Voir [Configuration Gateway](#configuration-gateway-traefik) ci-dessous pour l'installation complète.

## Configuration Gateway Traefik

### Installation rapide du Proxmox Provider

Sur votre Gateway Traefik (VPS/Cloud), créer `docker-compose.yml` :

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

    environment:
      - PROXMOX_ENDPOINT=https://VOTRE-IP-PROXMOX:8006/api2/json
      - PROXMOX_USERNAME=root@pam
      - PROXMOX_TOKEN_NAME=ansible
      - PROXMOX_TOKEN_VALUE=VOTRE-TOKEN-ICI
      - PROXMOX_INSECURE_SKIP_VERIFY=true
      - PROXMOX_POLL_INTERVAL=30s

    volumes:
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - ./acme.json:/etc/traefik/acme.json

    command:
      - "--providers.docker=false"
      - "--experimental.plugins.proxmox.modulename=github.com/NX211/traefik-proxmox-provider"
      - "--experimental.plugins.proxmox.version=v0.2.0"
```

Créer `traefik.yml` :

```yaml
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: votre.email@example.com
      storage: /etc/traefik/acme.json
      httpChallenge:
        entryPoint: web

experimental:
  plugins:
    proxmox:
      moduleName: "github.com/NX211/traefik-proxmox-provider"
      version: "v0.2.0"
```

Démarrer :

```bash
touch acme.json && chmod 600 acme.json
docker-compose up -d
```

**Le Gateway Traefik va maintenant automatiquement** :
1. Lire les notes Proxmox toutes les 30s
2. Détecter les labels Traefik
3. Configurer les routes automatiquement

## Commandes essentielles

### Découvrir et mettre à jour

```bash
# Mode pass-through (recommandé)
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml

# Mode filter
# Éditer playbooks/discover-and-update.yml : gateway_mode: "filter"
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml
```

### Vérifier les notes Proxmox

```bash
ansible-playbook playbooks/check-notes.yml -i inventory/my.proxmox.yml
```

### Lister les VMs découvertes

```bash
ansible-inventory -i inventory/my.proxmox.yml --list
```

### Tester le rôle sur une VM spécifique

```bash
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml --limit HomeLab
```

### Exécuter en mode debug

```bash
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml -vvv
```

### Lancer les tests unitaires

```bash
cd tests
python3 test_label_parsing.py
```

## Configuration rapide

### Mode Pass-through (défaut)

Dans `playbooks/discover-and-update.yml` :

```yaml
vars:
  gateway_mode: "passthrough"
  traefik_local_port: 8080
  gateway_service_name: "homelab-traefik"
```

**Résultat** : Le Gateway copie les rules et pointe tout vers le Traefik local

### Mode Filter

Dans `playbooks/discover-and-update.yml` :

```yaml
vars:
  gateway_mode: "filter"
```

**Résultat** : Le Gateway reçoit uniquement les labels essentiels

## Exemples de résultats

### Input : Container local

```yaml
traefik.enable=true
traefik.docker.network=traefik
traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)
traefik.http.routers.mash-miniflux.entrypoints=web
traefik.http.routers.mash-miniflux.middlewares=compression@file
traefik.http.services.mash-miniflux.loadbalancer.server.port=8080
```

### Output : Mode Pass-through

```yaml
traefik.enable=true
traefik.http.routers.miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)
traefik.http.routers.miniflux.entrypoints=websecure
traefik.http.routers.miniflux.service=homelab-traefik
traefik.http.routers.miniflux.tls=true
traefik.http.routers.miniflux.tls.certresolver=letsencrypt
traefik.http.services.homelab-traefik.loadbalancer.server.port=8080
traefik.http.services.homelab-traefik.loadbalancer.server.scheme=http
```

### Output : Mode Filter

```yaml
traefik.enable=true
traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)
traefik.http.routers.mash-miniflux.entrypoints=web
traefik.http.services.mash-miniflux.loadbalancer.server.port=8080
```

## Dépannage rapide

### Problème : Rôle non trouvé

```bash
# Vérifier ansible.cfg
cat ansible.cfg
# Devrait contenir : roles_path = roles
```

### Problème : Permission denied (Docker)

```bash
# Sur la VM, donner accès Docker à l'utilisateur ansible
sudo usermod -aG docker ansible
# Ou configurer sudo
echo "ansible ALL=(ALL) NOPASSWD: /usr/bin/docker" | sudo tee /etc/sudoers.d/ansible-docker
```

### Problème : 0 labels trouvés

```bash
# Vérifier que les containers ont des labels Traefik
ssh ansible@VM-IP
docker inspect CONTAINER-NAME | grep -i traefik
```

### Problème : "input device is not a TTY"

```bash
# Utiliser la commande Docker sans -it
docker run --rm -w /work \
  --mount type=bind,src=/opt/mash/mash-playbook,dst=/work \
  --mount type=bind,src=$HOME/.ssh,dst=/root/.ssh,ro \
  ansible-proxmox:latest \
  ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml
```

## Structure des fichiers

```
mash-playbook/
├── playbooks/
│   ├── discover-and-update.yml   ← Playbook principal
│   └── check-notes.yml           ← Vérification
├── roles/
│   └── docker_traefik_discovery/ ← Rôle Ansible
├── tests/
│   └── test_label_parsing.py     ← Tests (31 tests)
├── inventory/
│   └── my.proxmox.yml            ← Inventaire Proxmox
└── ansible.cfg                   ← Configuration Ansible
```

## Checklist de déploiement

### Côté Proxmox/Ansible

- [ ] API Token Proxmox créé avec permissions `VM.Audit` et `Sys.Audit`
- [ ] Inventaire `inventory/my.proxmox.yml` configuré
- [ ] Clés SSH configurées pour accès aux VMs
- [ ] VMs taguées avec `exposed`
- [ ] Docker installé sur les VMs
- [ ] Utilisateur `ansible` existe sur les VMs avec accès Docker
- [ ] Tests unitaires passent (`python3 tests/test_label_parsing.py`)
- [ ] Premier run Ansible réussi

### Côté Gateway Traefik

- [ ] Traefik Gateway déployé (VPS/Cloud)
- [ ] Proxmox Provider installé et configuré
- [ ] Variables d'environnement Proxmox configurées
- [ ] Let's Encrypt configuré
- [ ] Ports 80/443 ouverts sur le firewall
- [ ] Logs du provider affichent la connexion Proxmox réussie
- [ ] Test d'accès : `curl -I https://votre-domaine.com`

## Variables importantes

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `gateway_mode` | `filter` | Mode : `filter` ou `passthrough` |
| `traefik_local_port` | `8080` | Port du Traefik local |
| `gateway_service_name` | `homelab-traefik` | Nom du service Gateway |
| `proxmox_api_host` | - | IP/hostname Proxmox |
| `proxmox_api_token_secret` | - | Token API Proxmox |

## Vérification de l'intégration

### Test complet end-to-end

```bash
# 1. Sur Ansible : Mettre à jour les notes Proxmox
ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml

# 2. Vérifier les notes
ansible-playbook playbooks/check-notes.yml -i inventory/my.proxmox.yml

# 3. Sur le Gateway : Vérifier les logs du provider
docker logs traefik-gateway 2>&1 | grep -i proxmox

# Devrait afficher :
# - "Connected to Proxmox API"
# - "Found X VMs with Traefik labels"
# - "Updated Traefik configuration"

# 4. Tester l'accès depuis Internet
curl -I https://homelab.cy-bert.fr/miniflux

# Devrait retourner : HTTP/2 200
```

### Workflow automatisé (optionnel)

Pour automatiser la mise à jour :

```bash
# Créer un cron pour exécuter Ansible toutes les heures
crontab -e

# Ajouter :
0 * * * * cd /opt/mash/mash-playbook && ansible-playbook playbooks/discover-and-update.yml -i inventory/my.proxmox.yml >> /var/log/traefik-sync.log 2>&1
```

**Note** : Le Proxmox Provider poll déjà toutes les 30s, donc pas besoin de cron très fréquent. Une fois par heure ou manuellement suffit.

## Prochaines étapes

1. ✅ Configuration initiale Ansible
2. ✅ Premier run réussi
3. ✅ Gateway Traefik avec Proxmox Provider installé
4. 📖 Lire la [documentation complète](traefik-proxmox-automation.md)
5. 🔄 Optionnel : Automatiser avec cron
6. 📊 Monitorer les logs du provider
7. 🚀 Ajouter plus de services dans vos containers Docker

## Ressources

- [Documentation complète](traefik-proxmox-automation.md)
- [Tests unitaires](../tests/test_label_parsing.py)
- [Module parse_docker_labels.py](../roles/docker_traefik_discovery/library/parse_docker_labels.py)

---

**Besoin d'aide ?** Consultez la section [Dépannage](traefik-proxmox-automation.md#dépannage) dans la documentation complète.
