import json
import os
import uuid
from datetime import datetime
import boto3

dynamodb = boto3.resource('dynamodb')

# Instância das tabelas a partir das variáveis de ambiente configuradas no Terraform
table_diagnosticos = dynamodb.Table(os.environ.get('TABLE_DIAGNOSTICOS'))
table_usuarios     = dynamodb.Table(os.environ.get('TABLE_USUARIOS'))
table_linhas       = dynamodb.Table(os.environ.get('TABLE_LINHAS'))
table_equipamentos = dynamodb.Table(os.environ.get('TABLE_EQUIPAMENTOS'))
table_defeitos     = dynamodb.Table(os.environ.get('TABLE_DEFEITOS'))

def response_json(status_code, body):
    """Padroniza a resposta HTTP com suporte a CORS"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body, ensure_ascii=False)
    }

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
        acao = body.get('acao')

        # 1. BUSCAR DIAGNÓSTICO RÁPIDO (Mantém compatibilidade com o PWA)
        if acao == 'buscar_diagnostico' or ('codigo_erro' in body and not acao):
            codigo = body.get('codigo_erro')
            res = table_diagnosticos.get_item(Key={'codigo_erro': codigo})
            item = res.get('Item', {})
            return response_json(200, {
                'solucao': item.get('procedimento', 'Código de erro não localizado no sistema.')
            })

        # 2. GESTÃO DE USUÁRIOS
        elif acao == 'cadastrar_usuario':
            dados = body.get('dados', {})
            user_id = str(uuid.uuid4())
            item = {
                'id': user_id,
                'nome': dados.get('nome'),
                'sobrenome': dados.get('sobrenome'),
                'email': dados.get('email'),
                'telefone': dados.get('telefone'),
                'nivel': dados.get('nivel', 'tecnico'), # 'admin' ou 'tecnico'
                'ativo': True,
                'data_criacao': datetime.utcnow().isoformat()
            }
            table_usuarios.put_item(Item=item)
            return response_json(201, {'mensagem': 'Usuário cadastrado com sucesso', 'id': user_id})

        elif acao == 'listar_usuarios':
            res = table_usuarios.scan()
            return response_json(200, {'usuarios': res.get('Items', [])})

        # 3. GESTÃO DE LINHAS DE PRODUÇÃO
        elif acao == 'cadastrar_linha':
            dados = body.get('dados', {})
            linha_id = str(uuid.uuid4())
            item = {
                'id': linha_id,
                'nome': dados.get('nome'),
                'setor': dados.get('setor', '')
            }
            table_linhas.put_item(Item=item)
            return response_json(201, {'mensagem': 'Linha cadastrada com sucesso', 'id': linha_id})

        elif acao == 'listar_linhas':
            res = table_linhas.scan()
            return response_json(200, {'linhas': res.get('Items', [])})

        # 4. GESTÃO DE EQUIPAMENTOS
        elif acao == 'cadastrar_equipamento':
            dados = body.get('dados', {})
            eq_id = str(uuid.uuid4())
            item = {
                'id': eq_id,
                'nome': dados.get('nome'),
                'id_linha': dados.get('id_linha'),
                'tag_patrimonio': dados.get('tag_patrimonio', '')
            }
            table_equipamentos.put_item(Item=item)
            return response_json(201, {'mensagem': 'Equipamento cadastrado com sucesso', 'id': eq_id})

        elif acao == 'listar_equipamentos':
            res = table_equipamentos.scan()
            return response_json(200, {'equipamentos': res.get('Items', [])})

        # 5. REGISTRO DE DEFEITOS / OCORRÊNCIAS
        elif acao == 'registrar_defeito':
            dados = body.get('dados', {})
            def_id = str(uuid.uuid4())
            item = {
                'id': def_id,
                'id_linha': dados.get('id_linha'),
                'id_equipamento': dados.get('id_equipamento'),
                'id_user': dados.get('id_user'),
                'descricao': dados.get('descricao'),
                'solucao_aplicada': dados.get('solucao_aplicada', ''),
                'status': dados.get('status', 'Aberto'),
                'data_registro': datetime.utcnow().isoformat()
            }
            table_defeitos.put_item(Item=item)
            return response_json(201, {'mensagem': 'Defeito registrado com sucesso', 'id': def_id})

        elif acao == 'listar_defeitos':
            res = table_defeitos.scan()
            return response_json(200, {'defeitos': res.get('Items', [])})

        else:
            return response_json(400, {'erro': 'Ação não informada ou inválida.'})

    except Exception as e:
        return response_json(500, {'erro': str(e)})