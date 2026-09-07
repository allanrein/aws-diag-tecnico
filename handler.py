import json
import os
import uuid
import boto3

dynamodb = boto3.resource('dynamodb')

TABELA_DIAGNOSTICOS = os.environ.get('TABLE_DIAGNOSTICOS', 'diagnosticos_tecnicos')
TABELA_USUARIOS = os.environ.get('TABLE_USUARIOS', 'usuarios')
TABELA_LINHAS = os.environ.get('TABLE_LINHAS', 'linhas')
TABELA_EQUIPAMENTOS = os.environ.get('TABLE_EQUIPAMENTOS', 'equipamentos')

HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET,DELETE,PUT'
}

def build_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': HEADERS,
        'body': json.dumps(body, ensure_ascii=False)
    }

def lambda_handler(event, context):
    http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
    
    if http_method == 'OPTIONS':
        return build_response(200, {'message': 'CORS OK'})

    try:
        raw_path = event.get('rawPath', '').rstrip('/')
        if raw_path.startswith('/diagnostico') and raw_path != '/diagnosticos':
            raw_path = raw_path.replace('/diagnostico', '', 1)

        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except Exception:
                body = {}

        # ROTA: POST /login
        if raw_path == '/login' and http_method == 'POST':
            usuario = body.get('usuario')
            senha = body.get('senha')

            if not usuario or not senha:
                return build_response(400, {'error': 'Usuário e senha obrigatórios'})

            tabela = dynamodb.Table(TABELA_USUARIOS)
            resposta = tabela.get_item(Key={'id': usuario})
            item = resposta.get('Item')

            if item and item.get('senha') == senha:
                return build_response(200, {
                    'usuario': item.get('usuario', item.get('id')),
                    'role': item.get('role', 'tecnico')
                })
            return build_response(401, {'error': 'Usuário ou senha incorretos'})

        # ROTA: GET /linhas
        elif raw_path == '/linhas' and http_method == 'GET':
            tabela = dynamodb.Table(TABELA_LINHAS)
            resposta = tabela.scan()
            return build_response(200, resposta.get('Items', []))

        # ROTA: GET /equipamentos
        elif raw_path == '/equipamentos' and http_method == 'GET':
            tabela = dynamodb.Table(TABELA_EQUIPAMENTOS)
            resposta = tabela.scan()
            return build_response(200, resposta.get('Items', []))

        # ROTA: GET /usuarios
        elif raw_path == '/usuarios' and http_method == 'GET':
            tabela = dynamodb.Table(TABELA_USUARIOS)
            resposta = tabela.scan()
            itens = resposta.get('Items', [])
            for item in itens:
                item['senha'] = '***'
            return build_response(200, itens)

        # ROTA: POST /usuarios (Criar ou Editar)
        elif raw_path == '/usuarios' and http_method == 'POST':
            usuario_id = body.get('usuario')
            senha = body.get('senha')
            role = body.get('role', 'tecnico')

            if not usuario_id:
                return build_response(400, {'error': 'Nome de usuário obrigatório'})

            tabela = dynamodb.Table(TABELA_USUARIOS)
            
            # Se a senha não foi informada na edição, mantém a senha atual
            if not senha:
                user_existente = tabela.get_item(Key={'id': usuario_id}).get('Item')
                if user_existente:
                    senha = user_existente.get('senha')
                else:
                    return build_response(400, {'error': 'Senha é obrigatória para novos usuários'})

            dados_usuario = {
                'id': usuario_id,
                'usuario': usuario_id,
                'senha': senha,
                'role': role
            }
            tabela.put_item(Item=dados_usuario)
            return build_response(201, {'message': 'Usuário salvo com sucesso'})

        # ROTA: DELETE /usuarios (Excluir)
        elif raw_path == '/usuarios' and http_method == 'DELETE':
            params = event.get('queryStringParameters') or {}
            usuario_id = params.get('usuario') or body.get('usuario')

            if not usuario_id:
                return build_response(400, {'error': 'Usuário não especificado'})

            if usuario_id == 'admin':
                return build_response(400, {'error': 'Não é permitido excluir o usuário admin principal'})

            tabela = dynamodb.Table(TABELA_USUARIOS)
            tabela.delete_item(Key={'id': usuario_id})
            return build_response(200, {'message': 'Usuário excluído com sucesso'})

        # ROTA: GET /diagnosticos
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

        # ROTA: POST /diagnosticos (Registrar Ocorrência)
        elif raw_path == '/diagnosticos' and http_method == 'POST':
            tabela = dynamodb.Table(TABELA_DIAGNOSTICOS)
            novo_registro = {
                'codigo_erro': str(uuid.uuid4()),
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

    except Exception as e:
        return build_response(500, {'error': f'Erro interno no servidor: {str(e)}'})