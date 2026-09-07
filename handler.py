import json
import os
import uuid
import hmac
import hashlib
import base64
import time
import boto3

dynamodb = boto3.resource('dynamodb')

TABELA_DIAGNOSTICOS = os.environ.get('TABLE_DIAGNOSTICOS', 'diagnosticos_tecnicos')
TABELA_USUARIOS = os.environ.get('TABLE_USUARIOS', 'usuarios')
TABELA_LINHAS = os.environ.get('TABLE_LINHAS', 'linhas')
TABELA_EQUIPAMENTOS = os.environ.get('TABLE_EQUIPAMENTOS', 'equipamentos')

JWT_SECRET = os.environ.get('JWT_SECRET', 'chave-secreta-sistema-tecnicos-2026')

HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key',
    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET,DELETE,PUT'
}

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def generate_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
    
    signature_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), signature_input, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_jwt(token: str) -> dict:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        signature_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = base64url_encode(hmac.new(JWT_SECRET.encode('utf-8'), signature_input, hashlib.sha256).digest())
        
        if not hmac.compare_digest(signature_b64, expected_sig):
            return None
        
        payload = json.loads(base64url_decode(payload_b64).decode('utf-8'))
        if payload.get('exp') and time.time() > payload['exp']:
            return None
            
        return payload
    except Exception:
        return None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

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
                return build_response(400, {'error': 'Usuário e senha são obrigatórios'})

            tabela = dynamodb.Table(TABELA_USUARIOS)
            resposta = tabela.get_item(Key={'id': usuario})
            item = resposta.get('Item')

            senha_hash = hash_password(senha)
            if item and (item.get('senha') == senha_hash or item.get('senha') == senha):
                payload = {
                    'sub': item.get('usuario', item.get('id')),
                    'role': item.get('role', 'tecnico'),
                    'exp': int(time.time()) + (8 * 3600)
                }
                token = generate_jwt(payload)
                return build_response(200, {
                    'usuario': payload['sub'],
                    'role': payload['role'],
                    'token': token
                })
            return build_response(401, {'error': 'Usuário ou senha incorretos'})

        # Validação obrigatória de Token JWT
        auth_header = event.get('headers', {}).get('authorization', '')
        user_session = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user_session = verify_jwt(token)

        if not user_session:
            return build_response(401, {'error': 'Sessão inválida ou expirada. Faça login novamente.'})

        # ROTA: GET /linhas
        elif raw_path == '/linhas' and http_method == 'GET':
            tabela = dynamodb.Table(TABELA_LINHAS)
            return build_response(200, tabela.scan().get('Items', []))

        # ROTA: GET /equipamentos
        elif raw_path == '/equipamentos' and http_method == 'GET':
            tabela = dynamodb.Table(TABELA_EQUIPAMENTOS)
            return build_response(200, tabela.scan().get('Items', []))

        # ROTAS DE GESTÃO DE USUÁRIOS (Apenas Admin)
        elif raw_path == '/usuarios':
            if user_session.get('role') != 'admin':
                return build_response(403, {'error': 'Acesso negado. Requer perfil administrador.'})

            tabela = dynamodb.Table(TABELA_USUARIOS)

            if http_method == 'GET':
                itens = tabela.scan().get('Items', [])
                for item in itens:
                    item['senha'] = '***'
                return build_response(200, itens)

            elif http_method == 'POST':
                usuario_id = body.get('usuario')
                senha = body.get('senha')
                role = body.get('role', 'tecnico')

                if not usuario_id:
                    return build_response(400, {'error': 'Nome de usuário obrigatório'})

                dados_usuario = {
                    'id': usuario_id,
                    'usuario': usuario_id,
                    'role': role
                }

                if senha:
                    dados_usuario['senha'] = hash_password(senha)
                else:
                    user_existente = tabela.get_item(Key={'id': usuario_id}).get('Item')
                    if user_existente:
                        dados_usuario['senha'] = user_existente.get('senha')
                    else:
                        return build_response(400, {'error': 'Senha é obrigatória para novos usuários'})

                tabela.put_item(Item=dados_usuario)
                return build_response(201, {'message': 'Usuário salvo com sucesso'})

            elif http_method == 'DELETE':
                params = event.get('queryStringParameters') or {}
                usuario_id = params.get('usuario') or body.get('usuario')

                if usuario_id == 'admin':
                    return build_response(400, {'error': 'Não é permitido excluir o usuário admin principal'})

                tabela.delete_item(Key={'id': usuario_id})
                return build_response(200, {'message': 'Usuário excluído com sucesso'})

        # ROTAS DE DIAGNÓSTICOS / OCORRÊNCIAS
        elif raw_path == '/diagnosticos':
            tabela = dynamodb.Table(TABELA_DIAGNOSTICOS)

            if http_method == 'GET':
                params = event.get('queryStringParameters') or {}
                termo_busca = params.get('busca', '').lower()

                itens = tabela.scan().get('Items', [])
                if termo_busca:
                    itens = [
                        i for i in itens
                        if termo_busca in str(i.get('codigo_falha', '')).lower()
                        or termo_busca in str(i.get('descricao_solucao', '')).lower()
                        or termo_busca in str(i.get('id_linha', '')).lower()
                        or termo_busca in str(i.get('id_equipamento', '')).lower()
                    ]

                return build_response(200, itens)

            elif http_method == 'POST':
                novo_registro = {
                    'codigo_erro': str(uuid.uuid4()),
                    'id_linha': body.get('id_linha'),
                    'id_equipamento': body.get('id_equipamento'),
                    'id_tecnico': user_session.get('sub'),
                    'codigo_falha': body.get('codigo_falha'),
                    'descricao_solucao': body.get('descricao_solucao'),
                    'data': body.get('data')
                }
                tabela.put_item(Item=novo_registro)
                return build_response(201, {'message': 'Ocorrência salva com sucesso'})

            elif http_method == 'PUT':
                if user_session.get('role') != 'admin':
                    return build_response(403, {'error': 'Acesso negado. Apenas administradores podem editar.'})

                codigo_erro = body.get('codigo_erro')
                if not codigo_erro:
                    return build_response(400, {'error': 'Código do erro obrigatório.'})

                tabela.update_item(
                    Key={'codigo_erro': codigo_erro},
                    UpdateExpression="SET id_linha = :l, id_equipamento = :e, codigo_falha = :f, descricao_solucao = :s",
                    ExpressionAttributeValues={
                        ':l': body.get('id_linha'),
                        ':e': body.get('id_equipamento'),
                        ':f': body.get('codigo_falha'),
                        ':s': body.get('descricao_solucao')
                    }
                )
                return build_response(200, {'message': 'Ocorrência atualizada com sucesso'})

            elif http_method == 'DELETE':
                if user_session.get('role') != 'admin':
                    return build_response(403, {'error': 'Acesso negado. Apenas administradores podem excluir.'})

                params = event.get('queryStringParameters') or {}
                codigo_erro = params.get('codigo_erro') or body.get('codigo_erro')

                if not codigo_erro:
                    return build_response(400, {'error': 'Código do erro é obrigatório'})

                tabela.delete_item(Key={'codigo_erro': codigo_erro})
                return build_response(200, {'message': 'Ocorrência excluída com sucesso'})

        return build_response(404, {'error': 'Rota não encontrada'})

    except Exception as e:
        return build_response(500, {'error': f'Erro interno no servidor: {str(e)}'})