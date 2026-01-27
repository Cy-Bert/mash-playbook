#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Traefik Proxmox Automation
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: parse_docker_labels
short_description: Parse Docker Traefik labels for Proxmox notes
version_added: "1.0.0"
description:
    - Parses Docker container Traefik labels
    - Formats them for Proxmox VM/LXC notes (one label per line)
    - Organizes labels by type (routers, services, middlewares, general)
options:
    labels:
        description:
            - List of Traefik labels from Docker containers
            - Each label should be in format "key=value"
        required: true
        type: list
        elements: str
    vmid:
        description: Proxmox VM/LXC ID
        required: true
        type: int
author:
    - Traefik Proxmox Automation Team
'''

EXAMPLES = r'''
- name: Parse Traefik labels for Proxmox notes
  parse_docker_labels:
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik"
      - "traefik.http.routers.mash-miniflux.entrypoints=web"
      - "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)"
      - "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080"
    vmid: 106
  register: result

- name: Display formatted notes
  debug:
    msg: "{{ result.proxmox_notes }}"
'''

RETURN = r'''
changed:
    description: Always returns True
    type: bool
    returned: always
    sample: true
proxmox_notes:
    description: Formatted string with all labels (one per line, separated by \n)
    type: str
    returned: always
    sample: "traefik.enable=true\ntraefik.docker.network=traefik\n..."
parsed_labels:
    description: Dictionary organized by label type
    type: dict
    returned: always
    sample: {
        "general": {"enable": "true", "docker.network": "traefik"},
        "routers": {"mash-miniflux": {"entrypoints": "web"}},
        "services": {},
        "middlewares": {}
    }
labels_count:
    description: Total number of labels parsed
    type: int
    returned: always
    sample: 10
'''

import re

# Import AnsibleModule only when running as Ansible module
try:
    from ansible.module_utils.basic import AnsibleModule
    HAS_ANSIBLE = True
except ImportError:
    HAS_ANSIBLE = False


def filter_labels_for_gateway(labels):
    """
    Filter Docker Traefik labels to keep only those needed for Gateway Traefik with Proxmox Provider.

    This removes:
    - Docker-specific labels (traefik.docker.*)
    - Middleware definitions (traefik.http.middlewares.*)
    - Middleware references in routers (routers.*.middlewares)

    This keeps:
    - traefik.enable
    - Router configuration: rule, entrypoints, tls, priority, service
    - Service configuration: loadbalancer.server.port, loadbalancer.server.scheme

    Args:
        labels (list): List of label strings in format "key=value"

    Returns:
        list: Filtered list of labels suitable for Gateway Traefik
    """
    # Patterns for labels to KEEP
    allowed_patterns = [
        r'^traefik\.enable$',
        r'^traefik\.http\.routers\.[^.]+\.rule$',
        r'^traefik\.http\.routers\.[^.]+\.entrypoints$',
        r'^traefik\.http\.routers\.[^.]+\.tls$',
        r'^traefik\.http\.routers\.[^.]+\.tls\.certresolver$',
        r'^traefik\.http\.routers\.[^.]+\.priority$',
        r'^traefik\.http\.routers\.[^.]+\.service$',
        r'^traefik\.http\.services\.[^.]+\.loadbalancer\.server\.port$',
        r'^traefik\.http\.services\.[^.]+\.loadbalancer\.server\.scheme$',
    ]

    # Patterns for labels to EXCLUDE (takes priority over allowed)
    excluded_patterns = [
        r'^traefik\.docker\.',
        r'^traefik\.http\.middlewares\.',
        r'^traefik\.http\.routers\.[^.]+\.middlewares$',  # Remove middleware references
        r'^traefik\.tcp\.',
        r'^traefik\.udp\.',
    ]

    filtered_labels = []

    for label in labels:
        if '=' not in label:
            continue

        # Extract key (before =)
        key = label.split('=', 1)[0]

        # Check if excluded (priority)
        is_excluded = any(re.match(pattern, key) for pattern in excluded_patterns)
        if is_excluded:
            continue

        # Check if allowed
        is_allowed = any(re.match(pattern, key) for pattern in allowed_patterns)
        if is_allowed:
            filtered_labels.append(label)

    return filtered_labels


def generate_gateway_labels_passthrough(labels, traefik_local_port=8080, service_name="homelab-traefik"):
    """
    Generate Gateway Traefik labels in pass-through mode.

    Extracts router rules from local Docker labels and creates Gateway routers
    that forward to the local Traefik instance. Each router on the Gateway
    uses the SAME rule as the local container, but points to a single service
    (the local Traefik).

    Architecture:
        Gateway Traefik → copies rules → Local Traefik → routes to containers

    Args:
        labels (list): List of label strings from all containers
        traefik_local_port (int): Port of local Traefik (default: 8080)
        service_name (str): Name of the service pointing to local Traefik

    Returns:
        list: Gateway labels with copied rules and single service
    """
    # Extract routers with their rules
    routers = {}
    router_pattern = re.compile(r'^traefik\.http\.routers\.([^.]+)\.rule$')

    for label in labels:
        if '=' not in label:
            continue

        key, value = label.split('=', 1)

        # Check if this is a router rule
        match = router_pattern.match(key)

        if match:
            original_router_name = match.group(1)
            rule = value

            # Simplify router name (remove 'mash-' prefix if present)
            gateway_router_name = original_router_name.replace('mash-', '')

            routers[gateway_router_name] = {
                'rule': rule,
                'original_name': original_router_name
            }

    # Generate Gateway labels
    gateway_labels = ["traefik.enable=true"]

    # Create a Gateway router for each local router
    for router_name, router_data in sorted(routers.items()):
        gateway_labels.extend([
            f"traefik.http.routers.{router_name}.entrypoints=websecure",
            f"traefik.http.routers.{router_name}.rule={router_data['rule']}",
            f"traefik.http.routers.{router_name}.service={service_name}",
            f"traefik.http.routers.{router_name}.tls=true",
            f"traefik.http.routers.{router_name}.tls.certresolver=letsencrypt"
        ])

    # Single service pointing to local Traefik
    gateway_labels.extend([
        f"traefik.http.services.{service_name}.loadbalancer.server.port={traefik_local_port}",
        f"traefik.http.services.{service_name}.loadbalancer.server.scheme=http"
    ])

    return gateway_labels


def parse_traefik_labels(labels):
    """
    Parse Traefik labels and organize them by type.

    Args:
        labels (list): List of label strings in format "key=value"

    Returns:
        dict: Organized labels by type (general, routers, services, middlewares)
    """
    parsed = {
        'general': {},
        'routers': {},
        'services': {},
        'middlewares': {}
    }

    # Regex patterns for different label types
    patterns = {
        'router': re.compile(r'^traefik\.http\.routers\.([^.]+)\.(.+)$'),
        'service': re.compile(r'^traefik\.http\.services\.([^.]+)\.(.+)$'),
        'middleware': re.compile(r'^traefik\.http\.middlewares\.([^.]+)\.(.+)$'),
        'general': re.compile(r'^traefik\.(.+)$')
    }

    for label in labels:
        if '=' not in label:
            continue

        key, value = label.split('=', 1)

        # Check router pattern
        match = patterns['router'].match(key)
        if match:
            router_name = match.group(1)
            property_name = match.group(2)
            if router_name not in parsed['routers']:
                parsed['routers'][router_name] = {}
            parsed['routers'][router_name][property_name] = value
            continue

        # Check service pattern
        match = patterns['service'].match(key)
        if match:
            service_name = match.group(1)
            property_name = match.group(2)
            if service_name not in parsed['services']:
                parsed['services'][service_name] = {}
            parsed['services'][service_name][property_name] = value
            continue

        # Check middleware pattern
        match = patterns['middleware'].match(key)
        if match:
            middleware_name = match.group(1)
            property_name = match.group(2)
            if middleware_name not in parsed['middlewares']:
                parsed['middlewares'][middleware_name] = {}
            parsed['middlewares'][middleware_name][property_name] = value
            continue

        # Check general traefik pattern (but not http.routers/services/middlewares)
        match = patterns['general'].match(key)
        if match:
            # Skip if it's an http.routers/services/middlewares pattern
            if not key.startswith('traefik.http.'):
                property_name = match.group(1)
                parsed['general'][property_name] = value

    return parsed


def format_labels_for_proxmox(labels):
    """
    Format labels for Proxmox notes (one label per line).
    Always puts traefik.enable=true first if present.

    Args:
        labels (list): List of label strings

    Returns:
        str: Formatted string with labels separated by \n
    """
    if not labels:
        return ""

    # Separate traefik.enable from other labels
    enable_label = None
    other_labels = []

    for label in labels:
        if label.startswith('traefik.enable='):
            enable_label = label
        else:
            other_labels.append(label)

    # Sort other labels alphabetically for consistency
    other_labels.sort()

    # Build final list with enable first
    final_labels = []
    if enable_label:
        final_labels.append(enable_label)
    final_labels.extend(other_labels)

    return '\n'.join(final_labels)


def run_module():
    """Main module execution."""

    module_args = dict(
        labels=dict(type='list', required=True, elements='str'),
        vmid=dict(type='int', required=True),
        filter_for_gateway=dict(type='bool', required=False, default=True),
        gateway_mode=dict(type='str', required=False, default='filter', choices=['filter', 'passthrough']),
        traefik_local_port=dict(type='int', required=False, default=8080),
        gateway_service_name=dict(type='str', required=False, default='homelab-traefik')
    )

    result = dict(
        changed=True,
        proxmox_notes='',
        parsed_labels={},
        labels_count=0,
        labels_count_before_filter=0,
        gateway_mode='filter'
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    try:
        labels = module.params['labels']
        vmid = module.params['vmid']
        filter_for_gateway = module.params['filter_for_gateway']
        gateway_mode = module.params['gateway_mode']
        traefik_local_port = module.params['traefik_local_port']
        gateway_service_name = module.params['gateway_service_name']

        # Filter only traefik labels
        traefik_labels = [label for label in labels if label.startswith('traefik.')]
        result['labels_count_before_filter'] = len(traefik_labels)
        result['gateway_mode'] = gateway_mode

        # Choose processing mode
        if gateway_mode == 'passthrough':
            # Pass-through mode: Generate Gateway labels from local rules
            traefik_labels = generate_gateway_labels_passthrough(
                traefik_labels,
                traefik_local_port=traefik_local_port,
                service_name=gateway_service_name
            )
            result['msg'] = f"Generated {len(traefik_labels)} Gateway labels in pass-through mode from {result['labels_count_before_filter']} local labels"

        elif gateway_mode == 'filter':
            # Filter mode: Keep only relevant labels for Gateway
            if filter_for_gateway:
                traefik_labels = filter_labels_for_gateway(traefik_labels)
            result['msg'] = f"Filtered {result['labels_count_before_filter']} labels to {len(traefik_labels)} for gateway" if filter_for_gateway else f"Processed {len(traefik_labels)} labels"

        if not traefik_labels:
            result['proxmox_notes'] = ''
            result['parsed_labels'] = {
                'general': {},
                'routers': {},
                'services': {},
                'middlewares': {}
            }
            result['labels_count'] = 0
            result['changed'] = False
            result['msg'] = f"No labels generated in {gateway_mode} mode"
            module.exit_json(**result)

        # Parse labels
        parsed_labels = parse_traefik_labels(traefik_labels)

        # Format for Proxmox
        proxmox_notes = format_labels_for_proxmox(traefik_labels)

        # Update result
        result['proxmox_notes'] = proxmox_notes
        result['parsed_labels'] = parsed_labels
        result['labels_count'] = len(traefik_labels)
        result['changed'] = True

        module.exit_json(**result)

    except Exception as e:
        module.fail_json(msg=f"Error parsing labels: {str(e)}", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
