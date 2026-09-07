terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "allan-tfstate-sistema-tecnicos-2026"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}


provider "aws" {
  region = "us-east-1"
}

# ------------------------------------------------------------------------------
# 1. TABELAS NO DYNAMODB
# ------------------------------------------------------------------------------

# Tabela original de diagnósticos rápidos
resource "aws_dynamodb_table" "tabela_diagnosticos" {
  name         = "diagnosticos_tecnicos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "codigo_erro"

  attribute {
    name = "codigo_erro"
    type = "S"
  }
}

# Tabela de Usuários (Técnicos e Admins)
resource "aws_dynamodb_table" "tabela_usuarios" {
  name         = "usuarios"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Tabela de Linhas de Produção
resource "aws_dynamodb_table" "tabela_linhas" {
  name         = "linhas"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Tabela de Equipamentos
resource "aws_dynamodb_table" "tabela_equipamentos" {
  name         = "equipamentos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Tabela de Registro de Defeitos/Ocorrências
resource "aws_dynamodb_table" "tabela_defeitos" {
  name         = "defeitos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# ------------------------------------------------------------------------------
# 2. COMPACTAÇÃO DO CÓDIGO PYTHON (LAMBDA)
# ------------------------------------------------------------------------------

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "handler.py"
  output_path = "lambda_payload.zip"
}

# ------------------------------------------------------------------------------
# 3. SEGURANÇA E PERMISSÕES (IAM)
# ------------------------------------------------------------------------------

resource "aws_iam_role" "lambda_role" {
  name = "role_sistema_tecnicos_lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Permissão unificada para a Lambda acessar TODAS as tabelas
resource "aws_iam_role_policy" "lambda_policy" {
  name = "permissao_dynamodb_lambda"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
        "dynamodb:Query"
      ]
      Resource = [
        aws_dynamodb_table.tabela_diagnosticos.arn,
        aws_dynamodb_table.tabela_usuarios.arn,
        aws_dynamodb_table.tabela_linhas.arn,
        aws_dynamodb_table.tabela_equipamentos.arn,
        aws_dynamodb_table.tabela_defeitos.arn
      ]
    }]
  })
}

# ------------------------------------------------------------------------------
# 4. FUNÇÃO AWS LAMBDA
# ------------------------------------------------------------------------------

resource "aws_lambda_function" "api_lambda" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "buscar_diagnostico_tecnico"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      TABLE_DIAGNOSTICOS = aws_dynamodb_table.tabela_diagnosticos.name
      TABLE_USUARIOS     = aws_dynamodb_table.tabela_usuarios.name
      TABLE_LINHAS       = aws_dynamodb_table.tabela_linhas.name
      TABLE_EQUIPAMENTOS = aws_dynamodb_table.tabela_equipamentos.name
      TABLE_DEFEITOS     = aws_dynamodb_table.tabela_defeitos.name
    }
  }
}

# ------------------------------------------------------------------------------
# 5. API GATEWAY (COM CORS HABILITADO)
# ------------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "http_api" {
  name          = "api_sistema_tecnicos"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "api_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api_lambda.invoke_arn
  payload_format_version = "2.0"
}

# Captura QUALQUER rota e método no backend
resource "aws_apigatewayv2_route" "api_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Permissão Única de Invocação
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# ------------------------------------------------------------------------------
# 6. OUTPUTS
# ------------------------------------------------------------------------------

output "url_da_api" {
  value       = aws_apigatewayv2_api.http_api.api_endpoint
  description = "URL Base limpa para o frontend"
}