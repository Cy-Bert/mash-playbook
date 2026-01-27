#!/bin/bash
set -euo pipefail

OUTPUT_JSON=$(mktemp)

# Detect if we need sudo for Docker
DOCKER_CMD="docker"
if ! docker ps &> /dev/null; then
    if sudo docker ps &> /dev/null; then
        DOCKER_CMD="sudo docker"
    else
        echo '{"error": "Docker not accessible", "containers": []}'
        exit 0
    fi
fi

if ! command -v docker &> /dev/null; then
    echo '{"error": "Docker not installed", "containers": []}'
    exit 0
fi

CONTAINERS=$($DOCKER_CMD ps --format '{{.ID}}|{{.Names}}' 2>/dev/null || echo "")

if [ -z "$CONTAINERS" ]; then
    echo '{"containers": []}'
    exit 0
fi

echo '{"containers": [' > "$OUTPUT_JSON"

FIRST=true
while IFS='|' read -r CONTAINER_ID CONTAINER_NAME; do
    # Récupérer TOUS les labels, on filtrera avec grep
    LABELS=$($DOCKER_CMD inspect "$CONTAINER_ID" --format '{{range $key, $value := .Config.Labels}}{{printf "%s=%s\n" $key $value}}{{end}}' 2>/dev/null | grep '^traefik\.' || echo "")
    
    if [ -n "$LABELS" ]; then
        if [ "$FIRST" = false ]; then
            echo "," >> "$OUTPUT_JSON"
        fi
        FIRST=false
        
        cat >> "$OUTPUT_JSON" << CONTAINER_JSON
  {
    "id": "$CONTAINER_ID",
    "name": "$CONTAINER_NAME",
    "labels": [
CONTAINER_JSON
        
        FIRST_LABEL=true
        while IFS= read -r LABEL; do
            if [ -n "$LABEL" ]; then
                if [ "$FIRST_LABEL" = false ]; then
                    echo "," >> "$OUTPUT_JSON"
                fi
                FIRST_LABEL=false
                # Échapper les guillemets et backslashes dans le label
                ESCAPED_LABEL=$(echo "$LABEL" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
                echo "      \"$ESCAPED_LABEL\"" >> "$OUTPUT_JSON"
            fi
        done <<< "$LABELS"
        
        echo "    ]" >> "$OUTPUT_JSON"
        echo "  }" >> "$OUTPUT_JSON"
    fi
done <<< "$CONTAINERS"

echo "]}" >> "$OUTPUT_JSON"
cat "$OUTPUT_JSON"
rm -f "$OUTPUT_JSON"
