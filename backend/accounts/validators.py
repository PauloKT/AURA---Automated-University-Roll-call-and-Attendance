from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils.deconstruct import deconstructible


@deconstructible
class SpacedUsernameValidator(UnicodeUsernameValidator):
    regex = r'^[\w.@+\- ]+\Z'
    message = 'Use letras, números, espaços ou os caracteres @ . + - _.'

