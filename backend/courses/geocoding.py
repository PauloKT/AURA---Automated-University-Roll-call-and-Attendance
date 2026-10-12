"""Integração de geocodificação de instituições do AURA."""
from urllib.parse import urlencode

import requests


GEOCODING_URL = 'https://photon.komoot.io/api/'


def geocode_address(address: str) -> list[dict]:
    """Busca candidatos de coordenadas para um endereço completo.

    A resposta é uma lista de candidatos para permitir confirmação administrativa;
    o sistema não deve assumir que o primeiro resultado é necessariamente correto.
    """
    if not address.strip():
        return []

    try:
        response = requests.get(
            f'{GEOCODING_URL}?{urlencode({"q": address, "limit": 5})}',
            headers={'User-Agent': 'TCC-AURA/1.0'},
            timeout=10,
        )
        response.raise_for_status()
        candidates = []
        for item in response.json().get('features', []):
            coordinates = item.get('geometry', {}).get('coordinates', [])
            if len(coordinates) != 2:
                continue
            properties = item.get('properties', {})
            candidates.append({
                'latitude': coordinates[1],
                'longitude': coordinates[0],
                'nome': properties.get('name', ''),
                'cidade': properties.get('city', ''),
                'estado': properties.get('state', ''),
                'endereco': properties.get('street', ''),
            })
        return candidates
    except (requests.RequestException, ValueError, TypeError):
        return []
