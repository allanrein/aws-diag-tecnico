# ⚡ Diagnóstico Técnico Serverless (PWA + AWS)

Aplicação Web Progressiva (PWA) de arquitetura 100% Serverless projetada para registro, consulta e gestão de diagnósticos de falhas em manutenção industrial. O sistema conta com controle de acesso baseado em funções (RBAC), autenticação via JWT, provisionamento via Infraestrutura como Código (Terraform) e integração contínua (CI/CD) automatizada via GitHub Actions.

---

## 📐 Arquitetura do Sistema

```

[ Frontend: PWA / Single Page Application ]
(GitHub Pages)
│
│ HTTPS / REST (JSON) + Authorization: Bearer
▼
[ AWS API Gateway v2 (HTTP API) ]
│
│ Payload Format v2.0
▼
[ AWS Lambda (Python 3.11 / Boto3) ]
│
├─► Validação Token HMAC-SHA256 (JWT)
├─► Hash de Senha (SHA-256)
└─► IAM Role (Políticas de leitura/escrita)
│
▼
[ AWS DynamoDB (Single-Region NoSQL) ]
├── usuarios
├── diagnosticos_tecnicos
├── linhas
├── equipamentos
└── defeitos

```

---

## 🛠️ Tecnologias Utilizadas

- **Frontend:** HTML5, Tailwind CSS (via CDN), JavaScript Vanilla (ES6+ Single Page Application), Service Worker / Manifest PWA.
- **Hospedagem Frontend:** GitHub Pages.
- **Backend:** AWS Lambda (Python 3.11 com SDK `boto3`).
- **API Management:** AWS API Gateway v2 (HTTP API) com suporte a CORS Global e Payloads v2.0.
- **Banco de Dados:** AWS DynamoDB (On-Demand / Pay-Per-Request).
- **Infraestrutura como Código (IaC):** Terraform (`>= 1.5.0`) com Remote State persistido em S3 (`allan-tfstate-sistema-tecnicos-2026`).
- **CI/CD:** GitHub Actions (Deploy automático de IaC, Código Lambda e Frontend).
- **Segurança:** Autenticação via JSON Web Tokens (JWT HS256) nativo no Python, Hashing SHA-256 para credenciais e controle de permissões por perfil (RBAC).

---

## 🔐 Camadas de Segurança e Autenticação

1. **Geração e Validação de Tokens (JWT):**
   - O login gera um token assinado com `HMAC-SHA256` contendo `sub` (usuário), `role` (`admin` ou `tecnico`) e tempo de expiração (`exp` de 8 horas).
   - Todas as chamadas para rotas protegidas exigem o cabeçalho `Authorization: Bearer <token>`.

2. **Controle de Acesso Baseado em Funções (RBAC):**
   - **Técnico:** Permissão para consultar dados (`GET /diagnosticos`, `/linhas`, `/equipamentos`) e registrar novas ocorrências (`POST /diagnosticos`).
   - **Administrador:** Acesso irrestrito. Único perfil autorizado a editar/excluir ocorrências (`PUT`/`DELETE /diagnosticos`) e gerenciar contas de acesso (`GET`, `POST`, `DELETE /usuarios`).

3. **Proteção de Dados Sensíveis:**
   - Senhas armazenadas na tabela `usuarios` do DynamoDB passam por hashing `SHA-256` no backend.
   - Respostas de listagem de usuários omitem a exibição das senhas (`***`).

---

## 🗄️ Estrutura das Tabelas DynamoDB

| Tabela                  | Chave Primária (Partition Key) | Descrição                                                                 |
| :---------------------- | :----------------------------- | :------------------------------------------------------------------------ |
| `usuarios`              | `id` (String)                  | Cadastro de usuários, hashes de senhas e papéis (`admin`/`tecnico`).      |
| `diagnosticos_tecnicos` | `codigo_erro` (String)         | Histórico de falhas, soluções aplicadas, técnico responsável e timestamp. |
| `linhas`                | `id` (String)                  | Mapeamento de linhas de produção da planta industrial.                    |
| `equipamentos`          | `id` (String)                  | Cadastro de ativos de campo (inversores, PLCs, motores, etc.).            |
| `defeitos`              | `id` (String)                  | Tabela de suporte para códigos de erro padronizados.                      |

---

## 🔌 Documentação das Rotas da API

| Método   | Endpoint        | Protegido? | Perfil Mínimo | Descrição                                       |
| :------- | :-------------- | :--------- | :------------ | :---------------------------------------------- |
| `POST`   | `/login`        | Não        | Público       | Autentica o usuário e retorna o Token JWT.      |
| `GET`    | `/linhas`       | Sim        | Técnico       | Retorna as linhas de produção cadastradas.      |
| `GET`    | `/equipamentos` | Sim        | Técnico       | Retorna os equipamentos cadastrados.            |
| `GET`    | `/diagnosticos` | Sim        | Técnico       | Lista/Busca ocorrências registradas no sistema. |
| `POST`   | `/diagnosticos` | Sim        | Técnico       | Registra uma nova ocorrência técnica.           |
| `PUT`    | `/diagnosticos` | Sim        | **Admin**     | Atualiza dados de uma ocorrência existente.     |
| `DELETE` | `/diagnosticos` | Sim        | **Admin**     | Remove uma ocorrência pelo `codigo_erro`.       |
| `GET`    | `/usuarios`     | Sim        | **Admin**     | Lista todos os usuários cadastrados.            |
| `POST`   | `/usuarios`     | Sim        | **Admin**     | Cria ou edita usuários (senha/role).            |
| `DELETE` | `/usuarios`     | Sim        | **Admin**     | Remove um usuário (exceto o `admin` principal). |

---

## 🚀 Como Executar e Deployar

### Pré-requisitos

- **AWS CLI** configurada localmente (`aws configure`).
- **Terraform CLI** instalado (`v1.5.0+`).
- **Git** e conta no **GitHub**.

### 1. Provisionamento da Infraestrutura (Local)

```powershell
# Clonar o repositório
git clone [https://github.com/allanrein/aws-diag-tecnico.git](https://github.com/allanrein/aws-diag-tecnico.git)
cd aws-diag-tecnico

# Inicializar e aplicar o Terraform
terraform init
terraform plan
terraform apply -auto-approve

```

### 2. Cadastrar o Usuário Administrador Inicial (DynamoDB)

Execute o comando via AWS CLI para registrar a conta `admin` primária no DynamoDB:

```powershell
# Criar JSON temporário para evitar incompatibilidades de aspas no PowerShell
Set-Content -Path item_user.json -Value '{"id":{"S":"admin"},"usuario":{"S":"admin"},"senha":{"S":"admin123"},"role":{"S":"admin"}}'

# Enviar item para a tabela usuarios
aws dynamodb put-item --table-name usuarios --item file://item_user.json --region us-east-1

# Remover o arquivo temporário
Remove-Item item_user.json

```

### 3. Deploy Contínuo (CI/CD)

Toda alteração enviada para a branch `main` executa a pipeline do **GitHub Actions**, atualizando a função Lambda, aplicando eventuais mudanças no Terraform e publicando o PWA no **GitHub Pages**.

```powershell
git add .
git commit -m "feat: atualizações da aplicação"
git push origin main

```

---

## 👤 Autor

Desenvolvido por **Allan Rodrigo Rein**

- **GitHub:** [@allanrein](https://www.google.com/search?q=https://github.com/allanrein)
- **Atuação:** Automação Industrial e Engenharia de Software / Cloud

```

```
