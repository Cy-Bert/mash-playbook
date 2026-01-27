# Traefik Proxmox Automation - Guide de démarrage rapide

Guide condensé pour démarrer rapidement avec le système de découverte Traefik-Proxmox.

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

- [ ] API Token Proxmox créé
- [ ] Inventaire `inventory/my.proxmox.yml` configuré
- [ ] Clés SSH configurées pour accès aux VMs
- [ ] VMs taguées avec `exposed`
- [ ] Docker installé sur les VMs
- [ ] Utilisateur `ansible` existe sur les VMs avec accès Docker
- [ ] Gateway Traefik configuré pour lire les notes Proxmox
- [ ] Tests unitaires passent (`python3 tests/test_label_parsing.py`)
- [ ] Premier run réussi

## Variables importantes

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `gateway_mode` | `filter` | Mode : `filter` ou `passthrough` |
| `traefik_local_port` | `8080` | Port du Traefik local |
| `gateway_service_name` | `homelab-traefik` | Nom du service Gateway |
| `proxmox_api_host` | - | IP/hostname Proxmox |
| `proxmox_api_token_secret` | - | Token API Proxmox |

## Intégration avec Traefik Gateway

Le Gateway Traefik doit être configuré pour lire les notes Proxmox. Exemple avec File Provider :

```yaml
# Sur le Gateway, créer un script qui :
# 1. Récupère les notes Proxmox via API
# 2. Convertit en configuration Traefik
# 3. Écrit dans /etc/traefik/dynamic/

# Exemple de cron :
*/5 * * * * /usr/local/bin/sync-proxmox-to-traefik.sh
```

## Prochaines étapes

1. ✅ Configuration initiale
2. ✅ Premier run réussi
3. 📖 Lire la [documentation complète](traefik-proxmox-automation.md)
4. 🔧 Configurer le Gateway Traefik pour lire les notes
5. 🔄 Automatiser avec un cron/systemd timer
6. 📊 Monitorer les changements

## Ressources

- [Documentation complète](traefik-proxmox-automation.md)
- [Tests unitaires](../tests/test_label_parsing.py)
- [Module parse_docker_labels.py](../roles/docker_traefik_discovery/library/parse_docker_labels.py)

---

**Besoin d'aide ?** Consultez la section [Dépannage](traefik-proxmox-automation.md#dépannage) dans la documentation complète.
