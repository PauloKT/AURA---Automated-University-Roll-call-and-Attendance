from rest_framework import serializers
from .models import Instituicao, Materia, Turma, Aula, TurmaAluno

class MateriaSerializer(serializers.ModelSerializer):
    carga_horaria = serializers.IntegerField(min_value=1)
    frequencia_minima = serializers.IntegerField(min_value=0, max_value=100, required=False)
    professor_username = serializers.CharField(source='professor.username', read_only=True)

    class Meta:
        model = Materia
        fields = ['id', 'nome', 'codigo', 'carga_horaria', 'frequencia_minima', 'professor', 'professor_username', 'created_at']
        read_only_fields = ['professor', 'created_at']


class InstituicaoCatalogoSerializer(serializers.ModelSerializer):
    """Catálogo de cadastro sem endereço detalhado nem coordenadas."""

    localizacao_confirmada = serializers.SerializerMethodField()

    class Meta:
        model = Instituicao
        fields = ['id', 'nome', 'cidade', 'estado', 'localizacao_confirmada']

    def get_localizacao_confirmada(self, obj) -> bool:
        return obj.latitude is not None and obj.longitude is not None


class InstituicaoSerializer(serializers.ModelSerializer):
    """Expõe instituições ativas e suas coordenadas confirmadas."""

    endereco_completo = serializers.ReadOnlyField()

    class Meta:
        model = Instituicao
        fields = [
            'id', 'nome', 'logradouro', 'numero', 'bairro', 'cidade',
            'estado', 'pais', 'endereco_completo', 'latitude', 'longitude',
            'radius_meters', 'geocodificada_em', 'geocoding_source', 'ativa',
        ]
        read_only_fields = [
            'latitude', 'longitude', 'geocodificada_em', 'geocoding_source',
        ]

class TurmaSerializer(serializers.ModelSerializer):
    def validate_materia(self, materia):
        if materia.professor_id != self.context['request'].user.id:
            raise serializers.ValidationError('Selecione uma matéria sua.')
        return materia

    materia_nome = serializers.CharField(source='materia.nome', read_only=True)
    materia_codigo = serializers.CharField(source='materia.codigo', read_only=True)

    class Meta:
        model = Turma
        fields = ['id', 'nome', 'materia', 'materia_nome', 'materia_codigo', 'semestre', 'ano', 'link_acesso', 'codigo_acesso', 'ativa', 'created_at']
        read_only_fields = ['link_acesso', 'codigo_acesso', 'created_at']

class TurmaAlunoSerializer(serializers.ModelSerializer):
    def validate_turma(self, turma):
        if turma.materia.professor_id != self.context['request'].user.id:
            raise serializers.ValidationError('Selecione uma turma sua.')
        return turma

    aluno_username = serializers.CharField(source='aluno.username', read_only=True)
    turma_nome = serializers.CharField(source='turma.nome', read_only=True)

    class Meta:
        model = TurmaAluno
        fields = ['id', 'turma', 'aluno', 'aluno_username', 'turma_nome', 'data_entrada']
        read_only_fields = ['data_entrada']

class AulaSerializer(serializers.ModelSerializer):
    def validate_turma(self, turma):
        if turma.materia.professor_id != self.context['request'].user.id:
            raise serializers.ValidationError('Selecione uma turma sua.')
        return turma

    def validate(self, attrs):
        inicio = attrs.get('horario_inicio', getattr(self.instance, 'horario_inicio', None))
        fim = attrs.get('horario_fim', getattr(self.instance, 'horario_fim', None))
        if inicio is not None and fim is not None and fim <= inicio:
            raise serializers.ValidationError({'hora_fim': 'O fim deve ser posterior ao início.'})
        return attrs

    turma_nome = serializers.CharField(source='turma.nome', read_only=True)
    hora_inicio = serializers.TimeField(source='horario_inicio')
    hora_fim = serializers.TimeField(source='horario_fim')
    criada_em = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Aula
        fields = ['id', 'turma', 'turma_nome', 'titulo', 'data', 'hora_inicio', 'hora_fim', 'criada_em']
