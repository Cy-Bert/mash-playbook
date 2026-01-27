#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for parse_docker_labels module.
Tests the parsing and formatting of Traefik labels.
"""

import sys
import os
import unittest

# Add the module path to import the functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../roles/docker_traefik_discovery/library'))

from parse_docker_labels import parse_traefik_labels, format_labels_for_proxmox, filter_labels_for_gateway, generate_gateway_labels_passthrough


class TestTraefikLabelParsing(unittest.TestCase):
    """Test suite for Traefik label parsing."""

    def test_parse_simple_labels(self):
        """Test parsing of simple general labels."""
        labels = [
            "traefik.enable=true",
            "traefik.docker.network=traefik"
        ]

        result = parse_traefik_labels(labels)

        self.assertEqual(result['general']['enable'], 'true')
        self.assertEqual(result['general']['docker.network'], 'traefik')
        self.assertEqual(len(result['routers']), 0)
        self.assertEqual(len(result['services']), 0)
        self.assertEqual(len(result['middlewares']), 0)

    def test_parse_router_labels(self):
        """Test parsing of router labels."""
        labels = [
            "traefik.enable=true",
            "traefik.http.routers.mash-miniflux.entrypoints=web",
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.routers.mash-miniflux.service=mash-miniflux",
            "traefik.http.routers.mash-miniflux.middlewares=compression@file,mash-miniflux-slashless-redirect"
        ]

        result = parse_traefik_labels(labels)

        self.assertIn('mash-miniflux', result['routers'])
        self.assertEqual(result['routers']['mash-miniflux']['entrypoints'], 'web')
        self.assertEqual(result['routers']['mash-miniflux']['service'], 'mash-miniflux')
        self.assertIn('Host(`homelab.cy-bert.fr`)', result['routers']['mash-miniflux']['rule'])

    def test_parse_service_labels(self):
        """Test parsing of service labels."""
        labels = [
            "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080"
        ]

        result = parse_traefik_labels(labels)

        self.assertIn('mash-miniflux', result['services'])
        self.assertEqual(result['services']['mash-miniflux']['loadbalancer.server.port'], '8080')

    def test_parse_middleware_labels(self):
        """Test parsing of middleware labels."""
        labels = [
            "traefik.http.middlewares.mash-miniflux-slashless-redirect.redirectregex.regex=^(/miniflux)$",
            "traefik.http.middlewares.mash-miniflux-slashless-redirect.redirectregex.replacement=${1}/",
            "traefik.http.middlewares.mash-miniflux-add-response-headers.headers.customresponseheaders.X-XSS-Protection=1; mode=block"
        ]

        result = parse_traefik_labels(labels)

        self.assertIn('mash-miniflux-slashless-redirect', result['middlewares'])
        self.assertEqual(result['middlewares']['mash-miniflux-slashless-redirect']['redirectregex.regex'], '^(/miniflux)$')
        self.assertEqual(result['middlewares']['mash-miniflux-slashless-redirect']['redirectregex.replacement'], '${1}/')
        self.assertIn('mash-miniflux-add-response-headers', result['middlewares'])

    def test_parse_complete_miniflux_labels(self):
        """Test parsing of complete real-world miniflux labels."""
        labels = [
            "traefik.enable=true",
            "traefik.docker.network=traefik",
            "traefik.http.routers.mash-miniflux.entrypoints=web",
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.routers.mash-miniflux.service=mash-miniflux",
            "traefik.http.routers.mash-miniflux.middlewares=compression@file,mash-miniflux-slashless-redirect,mash-miniflux-add-response-headers",
            "traefik.http.middlewares.mash-miniflux-slashless-redirect.redirectregex.regex=^(/miniflux)$",
            "traefik.http.middlewares.mash-miniflux-slashless-redirect.redirectregex.replacement=${1}/",
            "traefik.http.middlewares.mash-miniflux-add-response-headers.headers.customresponseheaders.X-XSS-Protection=1; mode=block",
            "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080"
        ]

        result = parse_traefik_labels(labels)

        # Check general labels
        self.assertEqual(result['general']['enable'], 'true')
        self.assertEqual(result['general']['docker.network'], 'traefik')

        # Check router
        self.assertIn('mash-miniflux', result['routers'])
        self.assertEqual(len(result['routers']['mash-miniflux']), 4)

        # Check service
        self.assertIn('mash-miniflux', result['services'])

        # Check middlewares
        self.assertIn('mash-miniflux-slashless-redirect', result['middlewares'])
        self.assertIn('mash-miniflux-add-response-headers', result['middlewares'])

    def test_format_labels_for_proxmox(self):
        """Test formatting labels for Proxmox notes."""
        labels = [
            "traefik.docker.network=traefik",
            "traefik.http.routers.mash-miniflux.entrypoints=web",
            "traefik.enable=true"
        ]

        result = format_labels_for_proxmox(labels)

        # Check that enable is first
        lines = result.split('\n')
        self.assertEqual(lines[0], "traefik.enable=true")

        # Check that all labels are present
        self.assertEqual(len(lines), 3)
        self.assertIn("traefik.docker.network=traefik", result)
        self.assertIn("traefik.http.routers.mash-miniflux.entrypoints=web", result)

    def test_format_labels_sorted(self):
        """Test that labels are sorted (except enable first)."""
        labels = [
            "traefik.http.services.test.loadbalancer.server.port=8080",
            "traefik.http.routers.test.entrypoints=web",
            "traefik.docker.network=traefik",
            "traefik.enable=true"
        ]

        result = format_labels_for_proxmox(labels)
        lines = result.split('\n')

        # First should be enable
        self.assertEqual(lines[0], "traefik.enable=true")

        # Rest should be sorted
        self.assertTrue(lines[1] < lines[2] < lines[3])

    def test_empty_labels(self):
        """Test with empty labels list."""
        labels = []

        result = parse_traefik_labels(labels)

        self.assertEqual(len(result['general']), 0)
        self.assertEqual(len(result['routers']), 0)
        self.assertEqual(len(result['services']), 0)
        self.assertEqual(len(result['middlewares']), 0)

    def test_non_traefik_labels(self):
        """Test that non-Traefik labels are ignored."""
        labels = [
            "com.docker.compose.project=mash",
            "com.docker.compose.service=miniflux",
            "traefik.enable=true"
        ]

        result = parse_traefik_labels(labels)

        # Only traefik.enable should be parsed
        self.assertEqual(len(result['general']), 1)
        self.assertEqual(result['general']['enable'], 'true')

    def test_malformed_labels(self):
        """Test handling of malformed labels."""
        labels = [
            "traefik.enable=true",
            "invalid_label_without_equals",
            "traefik.docker.network=traefik"
        ]

        result = parse_traefik_labels(labels)

        # Should skip malformed label and parse valid ones
        self.assertEqual(result['general']['enable'], 'true')
        self.assertEqual(result['general']['docker.network'], 'traefik')

    def test_labels_with_special_characters(self):
        """Test labels containing special characters."""
        labels = [
            "traefik.http.routers.test.rule=Host(`example.com`) && PathPrefix(`/api`)",
            "traefik.http.middlewares.test.redirectregex.replacement=${1}/"
        ]

        result = parse_traefik_labels(labels)

        self.assertIn('test', result['routers'])
        self.assertIn('`', result['routers']['test']['rule'])
        self.assertIn('${1}', result['middlewares']['test']['redirectregex.replacement'])

    def test_multiple_routers(self):
        """Test parsing multiple routers."""
        labels = [
            "traefik.http.routers.router1.entrypoints=web",
            "traefik.http.routers.router1.rule=Host(`example1.com`)",
            "traefik.http.routers.router2.entrypoints=websecure",
            "traefik.http.routers.router2.rule=Host(`example2.com`)"
        ]

        result = parse_traefik_labels(labels)

        self.assertEqual(len(result['routers']), 2)
        self.assertIn('router1', result['routers'])
        self.assertIn('router2', result['routers'])
        self.assertEqual(result['routers']['router1']['entrypoints'], 'web')
        self.assertEqual(result['routers']['router2']['entrypoints'], 'websecure')


class TestProxmoxNotesFormatting(unittest.TestCase):
    """Test suite for Proxmox notes formatting."""

    def test_enable_always_first(self):
        """Test that traefik.enable is always first."""
        labels = [
            "traefik.http.services.test.loadbalancer.server.port=8080",
            "traefik.docker.network=traefik",
            "traefik.enable=true",
            "traefik.http.routers.test.entrypoints=web"
        ]

        result = format_labels_for_proxmox(labels)
        first_line = result.split('\n')[0]

        self.assertEqual(first_line, "traefik.enable=true")

    def test_newline_separator(self):
        """Test that labels are separated by newlines."""
        labels = [
            "traefik.enable=true",
            "traefik.docker.network=traefik"
        ]

        result = format_labels_for_proxmox(labels)

        self.assertEqual(result.count('\n'), 1)
        self.assertIn("traefik.enable=true\ntraefik.docker.network=traefik", result)

    def test_empty_list_returns_empty_string(self):
        """Test that empty list returns empty string."""
        labels = []

        result = format_labels_for_proxmox(labels)

        self.assertEqual(result, "")


class TestLabelFiltering(unittest.TestCase):
    """Test suite for Gateway Traefik label filtering."""

    def test_filter_keeps_essential_labels(self):
        """Test that essential labels are kept."""
        labels = [
            "traefik.enable=true",
            "traefik.http.routers.app.rule=Host(`test.com`)",
            "traefik.http.services.app.loadbalancer.server.port=8080"
        ]

        filtered = filter_labels_for_gateway(labels)

        self.assertEqual(len(filtered), 3)
        self.assertIn("traefik.enable=true", filtered)
        self.assertIn("traefik.http.routers.app.rule=Host(`test.com`)", filtered)
        self.assertIn("traefik.http.services.app.loadbalancer.server.port=8080", filtered)

    def test_filter_removes_docker_labels(self):
        """Test that docker.* labels are removed."""
        labels = [
            "traefik.enable=true",
            "traefik.docker.network=traefik",
            "traefik.http.routers.app.rule=Host(`test.com`)"
        ]

        filtered = filter_labels_for_gateway(labels)

        self.assertEqual(len(filtered), 2)
        self.assertNotIn("traefik.docker.network=traefik", filtered)
        self.assertIn("traefik.enable=true", filtered)
        self.assertIn("traefik.http.routers.app.rule=Host(`test.com`)", filtered)

    def test_filter_removes_middleware_definitions(self):
        """Test that middleware definitions are removed."""
        labels = [
            "traefik.enable=true",
            "traefik.http.middlewares.test.redirectregex.regex=^(/test)$",
            "traefik.http.middlewares.test.redirectregex.replacement=${1}/",
            "traefik.http.routers.app.rule=Host(`test.com`)"
        ]

        filtered = filter_labels_for_gateway(labels)

        # Middleware definitions should be removed
        self.assertNotIn("traefik.http.middlewares.test.redirectregex.regex=^(/test)$", filtered)
        self.assertNotIn("traefik.http.middlewares.test.redirectregex.replacement=${1}/", filtered)
        # But the router rule should remain
        self.assertIn("traefik.http.routers.app.rule=Host(`test.com`)", filtered)

    def test_filter_removes_middleware_references(self):
        """Test that middleware references in routers are removed."""
        labels = [
            "traefik.enable=true",
            "traefik.http.routers.app.rule=Host(`test.com`)",
            "traefik.http.routers.app.middlewares=compression@file,test-redirect"
        ]

        filtered = filter_labels_for_gateway(labels)

        # Middleware reference should be removed
        self.assertNotIn("traefik.http.routers.app.middlewares=compression@file,test-redirect", filtered)
        # But other router config should remain
        self.assertIn("traefik.http.routers.app.rule=Host(`test.com`)", filtered)

    def test_filter_real_world_miniflux_labels(self):
        """Test filtering with real miniflux labels."""
        labels = [
            "traefik.docker.network=traefik",
            "traefik.enable=true",
            "traefik.http.middlewares.mash-miniflux-add-response-headers.headers.customresponseheaders.Content-Security-Policy=frame-ancestors 'self'",
            "traefik.http.middlewares.mash-miniflux-add-response-headers.headers.customresponseheaders.X-XSS-Protection=1; mode=block",
            "traefik.http.middlewares.mash-miniflux-slashless-redirect.redirectregex.regex=^(/miniflux)$",
            "traefik.http.middlewares.mash-miniflux-slashless-redirect.redirectregex.replacement=${1}/",
            "traefik.http.routers.mash-miniflux.entrypoints=web",
            "traefik.http.routers.mash-miniflux.middlewares=compression@file,mash-miniflux-slashless-redirect,mash-miniflux-add-response-headers",
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.routers.mash-miniflux.service=mash-miniflux",
            "traefik.http.routers.mash-miniflux.tls=false",
            "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080"
        ]

        filtered = filter_labels_for_gateway(labels)

        # Expected: 6 labels (enable + 4 router props + 1 service prop)
        # Removed: docker.network, all middleware definitions, middleware reference
        expected_labels = [
            "traefik.enable=true",
            "traefik.http.routers.mash-miniflux.entrypoints=web",
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.routers.mash-miniflux.service=mash-miniflux",
            "traefik.http.routers.mash-miniflux.tls=false",
            "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080"
        ]

        self.assertEqual(len(filtered), len(expected_labels))
        for label in expected_labels:
            self.assertIn(label, filtered)

        # Verify removed labels
        self.assertNotIn("traefik.docker.network=traefik", filtered)
        self.assertNotIn("traefik.http.routers.mash-miniflux.middlewares=compression@file,mash-miniflux-slashless-redirect,mash-miniflux-add-response-headers", filtered)

        # Verify no middleware definitions
        for label in filtered:
            self.assertNotIn("middlewares.", label.split('=')[0])

    def test_filter_keeps_tls_certresolver(self):
        """Test that tls.certresolver is kept."""
        labels = [
            "traefik.enable=true",
            "traefik.http.routers.app.rule=Host(`test.com`)",
            "traefik.http.routers.app.tls=true",
            "traefik.http.routers.app.tls.certresolver=letsencrypt"
        ]

        filtered = filter_labels_for_gateway(labels)

        self.assertEqual(len(filtered), 4)
        self.assertIn("traefik.http.routers.app.tls.certresolver=letsencrypt", filtered)

    def test_filter_empty_list(self):
        """Test filtering with empty list."""
        labels = []

        filtered = filter_labels_for_gateway(labels)

        self.assertEqual(len(filtered), 0)

    def test_filter_only_excluded_labels(self):
        """Test filtering when all labels are excluded."""
        labels = [
            "traefik.docker.network=traefik",
            "traefik.http.middlewares.test.redirectregex.regex=^(/test)$",
            "traefik.tcp.routers.test.rule=HostSNI(`test.com`)"
        ]

        filtered = filter_labels_for_gateway(labels)

        self.assertEqual(len(filtered), 0)

    def test_filter_keeps_service_scheme(self):
        """Test that service scheme is kept."""
        labels = [
            "traefik.enable=true",
            "traefik.http.services.app.loadbalancer.server.port=8080",
            "traefik.http.services.app.loadbalancer.server.scheme=https"
        ]

        filtered = filter_labels_for_gateway(labels)

        self.assertEqual(len(filtered), 3)
        self.assertIn("traefik.http.services.app.loadbalancer.server.scheme=https", filtered)


class TestGatewayPassthrough(unittest.TestCase):
    """Test suite for Gateway pass-through mode."""

    def test_passthrough_single_router(self):
        """Test pass-through with single router."""
        labels = [
            "traefik.enable=true",
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080"
        ]

        gateway_labels = generate_gateway_labels_passthrough(labels)

        # Check enable
        self.assertIn("traefik.enable=true", gateway_labels)

        # Check router with SAME rule
        self.assertIn("traefik.http.routers.miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.entrypoints=websecure", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.tls=true", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.tls.certresolver=letsencrypt", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.service=homelab-traefik", gateway_labels)

        # Check single service
        self.assertIn("traefik.http.services.homelab-traefik.loadbalancer.server.port=8080", gateway_labels)
        self.assertIn("traefik.http.services.homelab-traefik.loadbalancer.server.scheme=http", gateway_labels)

    def test_passthrough_multiple_routers(self):
        """Test pass-through with multiple routers."""
        labels = [
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.routers.mash-homarr.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/homarr`)",
            "traefik.http.routers.mash-autre.rule=Host(`autre.cy-bert.fr`)"
        ]

        gateway_labels = generate_gateway_labels_passthrough(labels)

        # Check all routers are created
        self.assertIn("traefik.http.routers.miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)", gateway_labels)
        self.assertIn("traefik.http.routers.homarr.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/homarr`)", gateway_labels)
        self.assertIn("traefik.http.routers.autre.rule=Host(`autre.cy-bert.fr`)", gateway_labels)

        # Check all point to same service
        miniflux_service_count = sum(1 for label in gateway_labels if "miniflux.service=homelab-traefik" in label)
        homarr_service_count = sum(1 for label in gateway_labels if "homarr.service=homelab-traefik" in label)
        autre_service_count = sum(1 for label in gateway_labels if "autre.service=homelab-traefik" in label)

        self.assertEqual(miniflux_service_count, 1)
        self.assertEqual(homarr_service_count, 1)
        self.assertEqual(autre_service_count, 1)

        # Check only ONE service definition
        service_definitions = [label for label in gateway_labels if "services.homelab-traefik." in label]
        self.assertEqual(len(service_definitions), 2)  # port + scheme

    def test_passthrough_removes_mash_prefix(self):
        """Test that 'mash-' prefix is removed from router names."""
        labels = [
            "traefik.http.routers.mash-miniflux.rule=Host(`test.com`)"
        ]

        gateway_labels = generate_gateway_labels_passthrough(labels)

        # Router should be named 'miniflux' not 'mash-miniflux'
        self.assertIn("traefik.http.routers.miniflux.rule=Host(`test.com`)", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.service=homelab-traefik", gateway_labels)

        # Should NOT contain mash-miniflux
        mash_labels = [label for label in gateway_labels if "mash-miniflux" in label]
        self.assertEqual(len(mash_labels), 0)

    def test_passthrough_custom_port_and_service(self):
        """Test pass-through with custom port and service name."""
        labels = [
            "traefik.http.routers.test.rule=Host(`test.com`)"
        ]

        gateway_labels = generate_gateway_labels_passthrough(
            labels,
            traefik_local_port=9000,
            service_name="custom-service"
        )

        self.assertIn("traefik.http.routers.test.service=custom-service", gateway_labels)
        self.assertIn("traefik.http.services.custom-service.loadbalancer.server.port=9000", gateway_labels)

    def test_passthrough_real_world_miniflux_homarr(self):
        """Test pass-through with real miniflux + homarr labels."""
        labels = [
            "traefik.docker.network=traefik",
            "traefik.enable=true",
            "traefik.http.routers.mash-miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)",
            "traefik.http.routers.mash-miniflux.entrypoints=web",
            "traefik.http.routers.mash-miniflux.middlewares=compression@file",
            "traefik.http.services.mash-miniflux.loadbalancer.server.port=8080",
            "traefik.http.routers.mash-homarr.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/homarr`)",
            "traefik.http.services.mash-homarr.loadbalancer.server.port=7575"
        ]

        gateway_labels = generate_gateway_labels_passthrough(labels)

        # Verify structure
        self.assertIn("traefik.enable=true", gateway_labels)

        # Verify miniflux router
        self.assertIn("traefik.http.routers.miniflux.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/miniflux`)", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.entrypoints=websecure", gateway_labels)
        self.assertIn("traefik.http.routers.miniflux.tls=true", gateway_labels)

        # Verify homarr router
        self.assertIn("traefik.http.routers.homarr.rule=Host(`homelab.cy-bert.fr`) && PathPrefix(`/homarr`)", gateway_labels)
        self.assertIn("traefik.http.routers.homarr.entrypoints=websecure", gateway_labels)

        # Verify both point to same service
        self.assertIn("traefik.http.routers.miniflux.service=homelab-traefik", gateway_labels)
        self.assertIn("traefik.http.routers.homarr.service=homelab-traefik", gateway_labels)

        # Verify no Docker-specific labels
        docker_labels = [label for label in gateway_labels if "docker" in label]
        self.assertEqual(len(docker_labels), 0)

        # Verify no middleware references
        middleware_refs = [label for label in gateway_labels if "middlewares=" in label]
        self.assertEqual(len(middleware_refs), 0)

    def test_passthrough_preserves_complex_rules(self):
        """Test that complex routing rules are preserved exactly."""
        labels = [
            "traefik.http.routers.test.rule=Host(`example.com`) && (PathPrefix(`/api`) || PathPrefix(`/admin`))"
        ]

        gateway_labels = generate_gateway_labels_passthrough(labels)

        # Rule should be preserved exactly
        self.assertIn("traefik.http.routers.test.rule=Host(`example.com`) && (PathPrefix(`/api`) || PathPrefix(`/admin`))", gateway_labels)

    def test_passthrough_empty_labels(self):
        """Test pass-through with no router labels."""
        labels = [
            "traefik.enable=true",
            "traefik.docker.network=traefik"
        ]

        gateway_labels = generate_gateway_labels_passthrough(labels)

        # Should only have enable and service (no routers)
        self.assertIn("traefik.enable=true", gateway_labels)
        self.assertIn("traefik.http.services.homelab-traefik.loadbalancer.server.port=8080", gateway_labels)

        # No routers should be created
        router_labels = [label for label in gateway_labels if ".routers." in label]
        self.assertEqual(len(router_labels), 0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
