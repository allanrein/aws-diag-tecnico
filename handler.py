import json
import os
import uuid
import boto3

# Inicialização do SDK do DynamoDB
dynamodb = boto3.resource('dynamodb')

# Nomes das tabelas no DynamoDB (podem vir de variáveis de ambiente ou do padrão do main.tf)
TABELA_DIAGNOSTICOS = os.environ.get('TABELA_DIAGNOSTICOS', 'diagnosticos_tecnicos')
TABELA_USUARIOS = os.environ.get('TABELA_USUARIOS', 'usuarios')
TABELA_LINHAS = os.environ.get('TABELA_LINHAS', 'linhas')
TABELA_EQUIPAMENTOS = os.environ.get('TABELA_EQUIPAMENTOS', 'equipamentos')

# Cabeçalhos padrão para habilitar CORS
HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
}

def build_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': HEADERS,
        'body': json.dumps(body, ensure_ascii=False)
    }

def lambda_handler(event, context):
    http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
    raw_path = event.get('rawPath', '')

    # Tratamento para requisições Preflight (CORS)
    if http_method == 'OPTIONS':
        return build_response(200, {'message': 'CORS OK'})

    try:
        body = json.loads(event.get('body') or '{}')
    except Exception:
        body = {}

    # ROTA: POST /login
    # ROTA: POST /login
    if raw_path == '/login' and http_method == 'POST':
        usuario = body.get('usuario')
        senha = body.get('senha')

        tabela = dynamodb.Table(TABELA_USUARIOS)
        # Ajustado para consultar a chave primária 'id'
        resposta = tabela.get_item(Key={'id': usuario})
        item = resposta.get('Item')

        if item and item.get('senha') == senha:
            return build_response(200, {
                'usuario': item.get('usuario', item.get('id')),
                'role': item.get('role', 'tecnico')
            })
        return build_response(401, {'error': 'Usuário ou senha incorretos'})

    # ROTA: GET /linhas (Para popular o menu suspenso)
    elif raw_path == '/linhas' and http_method == 'GET':
        tabela = dynamodb.Table(TABELA_LINHAS)
        resposta = tabela.scan()
        return build_response(200, resposta.get('Items', []))

    # ROTA: GET /equipamentos (Para popular o menu suspenso)
    elif raw_path == '/equipamentos' and http_method == 'GET':
        tabela = dynamodb.Table(TABELA_EQUIPAMENTOS)
        resposta = tabela.scan()
        return build_response(200, resposta.get('Items', []))

    # ROTA: GET /usuarios (Área de administração)
    elif raw_path == '/usuarios' and http_method == 'GET':
        tabela = dynamodb.Table(TABELA_USUARIOS)
        resposta = tabela.scan()
        itens = resposta.get('Items', [])
        for item in itens:
            item['senha'] = '***'  # Oculta a senha em listagens gerais
        return build_response(200, itens)

    # ROTA: POST /usuarios (Criar ou atualizar senhas/funções)
    elif raw_path == '/usuarios' and http_method == 'POST':
        tabela = dynamodb.Table(TABELA_USUARIOS)
        dados_usuario = {
            'usuario': body.get('usuario'),
            'senha': body.get('senha'),
            'role': body.get('role', 'tecnico')
        }
        tabela.put_item(Item=dados_usuario)
        return build_response(201, {'message': 'Usuário salvo com sucesso'})

    # ROTA: GET /diagnosticos (Busca de ocorrências registradas)
    elif raw_path == '/diagnosticos' and http_method == 'GET':
        tabela = dynamodb.Table(TABELA_DIAGNOSTICOS)
        params = event.get('queryStringParameters') or {}
        termo_busca = params.get('busca', '').lower()

        resposta = tabela.scan()
        itens = resposta.get('Items', [])

        if termo_busca:
            itens = [
                i for i in itens
                if termo_busca in str(i.get('codigo_falha', '')).lower()
                or termo_busca in str(i.get('descricao_solucao', '')).lower()
                or termo_busca in str(i.get('id_linha', '')).lower()
                or termo_busca in str(i.get('id_equipamento', '')).lower()
            ]

        return build_response(200, itens)

    # ROTA: POST /diagnosticos (Registrar nova ocorrência técnica)
    elif raw_path == '/diagnosticos' and http_method == 'POST':
        tabela = dynamodb.Table(TABELA_DIAGNOSTICOS)
        novo_registro = {
            'id': str(uuid.uuid4()),
            'id_linha': body.get('id_linha'),
            'id_equipamento': body.get('id_equipamento'),
            'id_tecnico': body.get('id_tecnico'),
            'codigo_falha': body.get('codigo_falha'),
            'descricao_solucao': body.get('descricao_solucao'),
            'data': body.get('data')
        }
        tabela.put_item(Item=novo_registro)
        return build_response(201, {'message': 'Ocorrência salva com sucesso'})

    return build_response(404, {'error': 'Rota não encontrada'})