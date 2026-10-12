"""QR em SVG gerado em memória, sem enviar o token a serviços externos."""
from base64 import b64encode
from urllib.parse import urlencode

import qrcode
from qrcode.image.svg import SvgPathFillImage
from django.urls import reverse
from rest_framework.exceptions import ValidationError


def session_qr_image(request, sessao):
    # O navegador conhece a origem pública mesmo atrás do túnel HTTPS.
    # Aceitamos apenas a origem do mesmo host validado pelo Django.
    host = request.get_host()
    origin = request.query_params.get('origin', f'{request.scheme}://{host}')
    if origin not in (f'http://{host}', f'https://{host}'):
        raise ValidationError({'origin': 'A origem do QR deve usar o mesmo host do painel.'})
    query = urlencode({'sessaoId': sessao.pk, 'token': sessao.token_atual})
    url = f'{origin}{reverse("presence-page")}?{query}'
    svg = qrcode.make(url, image_factory=SvgPathFillImage, border=4).to_string()
    return 'data:image/svg+xml;base64,' + b64encode(svg).decode('ascii')
