from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from courses.models import Instituicao

User = get_user_model()

class NovaInstituicaoSerializer(serializers.ModelSerializer):
    """Cadastro de campus sem autorização para definir coordenadas ou raio."""

    class Meta:
        model = Instituicao
        fields = ('nome', 'logradouro', 'numero', 'bairro', 'cidade', 'estado')

    def validate_nome(self, value):
        if Instituicao.objects.filter(nome__iexact=value).exists():
            raise serializers.ValidationError('Esta instituição já está cadastrada. Selecione-a na lista ou contate o administrador se a localização estiver pendente.')
        return value

    def validate_estado(self, value):
        value = value.upper()
        if value not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():
            raise serializers.ValidationError('Informe uma UF válida, como MS ou SP.')
        return value

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True, label="Confirmar senha")
    nova_instituicao = NovaInstituicaoSerializer(required=False, write_only=True)
    instituicoes = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Instituicao.objects.filter(ativa=True),
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'matricula', 'instituicao', 'instituicoes', 'nova_instituicao', 'password', 'password2')
        extra_kwargs = {
            'email': {'required': True, 'allow_blank': False},
        }

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Informe um nome de usuário.')
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este nome de usuário já está em uso.')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists() or User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Este e-mail já está em uso. Entre na sua conta.')
        return value

    def validate_password(self, value):
        errors = []
        if len(value) < 5:
            errors.append("A senha deve ter pelo menos 5 caracteres.")
        if not any(char.isdigit() for char in value):
            errors.append("A senha deve conter pelo menos um número.")
        if not any(char.isupper() for char in value):
            errors.append("A senha deve conter pelo menos uma letra maiúscula.")
        if not any(not char.isalnum() and not char.isspace() for char in value):
            errors.append("A senha deve conter pelo menos um caractere especial.")
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "As senhas não coincidem."})
        return self.validate_academic(attrs)

    def validate_academic(self, attrs):
        if attrs.get('role') == 'aluno' and not attrs.get('matricula'):
            raise serializers.ValidationError({"matricula": "Matrícula é obrigatória para alunos."})

        nova_instituicao = attrs.get('nova_instituicao')
        if nova_instituicao and attrs.get('role') != 'professor':
            raise serializers.ValidationError({'nova_instituicao': 'Somente o cadastro de professor pode adicionar uma instituição.'})

        if attrs.get('role') == 'professor':
            instituicoes = attrs.get('instituicoes', [])
            instituicao = attrs.get('instituicao')
            if nova_instituicao and (instituicoes or instituicao):
                raise serializers.ValidationError({'nova_instituicao': 'Escolha instituições existentes ou cadastre uma nova.'})
            if not instituicoes and instituicao:
                instituicoes = [instituicao]
                attrs['instituicoes'] = instituicoes
            if (not instituicoes and not nova_instituicao) or not all(instituicao.ativa for instituicao in instituicoes):
                raise serializers.ValidationError({
                    'instituicao': 'Selecione ao menos uma instituição ativa para professores.'
                })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Cria conta e campus juntos; erro no cadastro não deixa instituição órfã."""
        validated_data.pop('password2')
        password = validated_data.pop('password')
        instituicoes = validated_data.pop('instituicoes', [])
        nova_instituicao = validated_data.pop('nova_instituicao', None)
        if nova_instituicao:
            # Endereço não é geocodificado automaticamente: a confirmação continua administrativa.
            instituicoes = [Instituicao.objects.create(**nova_instituicao)]
        if instituicoes and not validated_data.get('instituicao'):
            validated_data['instituicao'] = instituicoes[0]
        user = User.objects.create_user(password=password, **validated_data)
        if instituicoes:
            user.instituicoes.set(instituicoes)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'role': self.user.role,
            }
        })
        return data
