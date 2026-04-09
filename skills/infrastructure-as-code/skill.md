---
name: infrastructure-as-code
description: Terraform and IaC patterns: resource lifecycle, remote state (S3+DynamoDB / GCS), module structure, workspace vs directory-per-environment, plan/apply workflow with OPA policy checks, drift detection, terraform import, and common AWS/GCP resource patterns.
---

# Infrastructure as Code

Terraform lets you define, provision, and version cloud infrastructure as declarative HCL code, enabling repeatable and reviewable infrastructure changes.

## When to Activate

- Writing Terraform for cloud resources (VPC, RDS, EKS, IAM, etc.)
- Setting up a Terraform state backend
- Creating a reusable Terraform module
- Managing multiple environments (dev/staging/prod) with Terraform
- Reviewing a `terraform plan` before applying
- Dealing with state drift or importing existing resources

## Core Building Blocks

```hcl
# Provider — connects Terraform to a cloud API
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variable — parameterise configuration
variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "Must be a valid AWS region code."
  }
}

# Local — computed values used inside the module
locals {
  name_prefix = "${var.environment}-${var.app_name}"
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    App         = var.app_name
  }
}

# Resource — a cloud resource
resource "aws_s3_bucket" "app_data" {
  bucket = "${local.name_prefix}-app-data"
  tags   = local.common_tags
}

# Data source — read existing resource without managing it
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# Output — export values for other modules or humans
output "s3_bucket_arn" {
  value       = aws_s3_bucket.app_data.arn
  description = "ARN of the application data bucket"
}
```

## State Management

### Remote State Backend

State must be remote and locked — never store `terraform.tfstate` in git.

**AWS (S3 + DynamoDB lock):**
```hcl
terraform {
  backend "s3" {
    bucket         = "my-org-terraform-state"
    key            = "services/payment-service/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"  # partition key: LockID (String)
  }
}
```

**GCP (GCS):**
```hcl
terraform {
  backend "gcs" {
    bucket = "my-org-terraform-state"
    prefix = "services/payment-service"
  }
}
```

### State Commands

```bash
terraform state list                      # list all managed resources
terraform state show aws_s3_bucket.data   # inspect a resource's state
terraform state mv OLD_ADDR NEW_ADDR      # rename without destroying
terraform state rm aws_s3_bucket.old      # remove from state (doesn't destroy)
terraform force-unlock LOCK_ID            # release a stuck lock
```

**State file security:** The state file contains sensitive values (RDS passwords, private keys). Ensure S3 bucket has:
- Versioning enabled (recover from bad apply)
- Server-side encryption
- Block public access
- Access restricted to CI role + team IAM role only

## Module Structure

```
modules/
└── rds-postgres/
    ├── main.tf        # resources
    ├── variables.tf   # inputs
    ├── outputs.tf     # outputs
    └── README.md      # usage docs (required for shared modules)
```

### Module Example

```hcl
# modules/rds-postgres/variables.tf
variable "instance_class" {
  type    = string
  default = "db.t3.medium"
}
variable "db_name"      { type = string }
variable "subnet_ids"   { type = list(string) }
variable "vpc_id"       { type = string }
variable "tags"         { type = map(string); default = {} }

# modules/rds-postgres/outputs.tf
output "endpoint"   { value = aws_db_instance.this.endpoint }
output "db_name"    { value = aws_db_instance.this.db_name }
output "secret_arn" { value = aws_secretsmanager_secret.db_password.arn }

# Consuming the module
module "payment_db" {
  source = "../../modules/rds-postgres"

  db_name        = "payments"
  instance_class = "db.t3.large"
  subnet_ids     = module.vpc.private_subnet_ids
  vpc_id         = module.vpc.vpc_id
  tags           = local.common_tags
}
```

### Module Versioning

```hcl
# Pin to a Git tag (preferred for shared modules)
module "rds" {
  source = "git::https://github.com/my-org/tf-modules.git//rds-postgres?ref=v2.1.0"
}

# Terraform Registry
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
}
```

## Environment Strategy

### Directory-per-Environment (recommended)

```
infra/
├── modules/
│   ├── vpc/
│   └── rds-postgres/
└── environments/
    ├── dev/
    │   ├── main.tf          # calls modules
    │   ├── terraform.tfvars # dev-specific values
    │   └── backend.tf       # dev state backend
    ├── staging/
    │   └── ...
    └── prod/
        └── ...
```

Pros: complete isolation, different providers per env, easy to `cd` into.
Cons: some code duplication across environments.

### Workspace (alternative)

```bash
terraform workspace new dev
terraform workspace select staging
terraform workspace list
```

Use `terraform.workspace` in HCL:
```hcl
locals {
  instance_type = terraform.workspace == "prod" ? "db.r6g.xlarge" : "db.t3.medium"
}
```

**Decision:** Use directory-per-environment for significant infrastructure differences between envs. Use workspaces only for identical infrastructure with minor variable differences.

### tfvars per Environment

```hcl
# environments/prod/terraform.tfvars
aws_region     = "us-east-1"
environment    = "prod"
instance_class = "db.r6g.xlarge"
min_capacity   = 3
max_capacity   = 20
```

## Plan/Apply Workflow

```bash
# 1. Init (first time, or after source changes)
terraform init

# 2. Format and validate
terraform fmt -recursive
terraform validate

# 3. Plan — save output for reproducible apply
terraform plan -out=tfplan -var-file=terraform.tfvars

# 4. Policy check (optional, using OPA/Conftest)
terraform show -json tfplan | conftest test -

# 5. Apply from the saved plan (no re-planning)
terraform apply tfplan

# 6. Verify
terraform state list
```

### CI Pipeline Integration

```yaml
# .github/workflows/terraform.yml
jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.7.0"
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/terraform-plan
          aws-region: us-east-1
      - run: terraform init
      - run: terraform plan -out=tfplan
      - run: terraform show -json tfplan > tfplan.json
      - name: Policy check
        run: conftest test tfplan.json --policy policies/
      - uses: actions/upload-artifact@v4
        with:
          name: tfplan
          path: tfplan

  apply:
    needs: plan
    if: github.ref == 'refs/heads/main'
    environment: production   # requires approval in GitHub
    steps:
      - uses: actions/download-artifact@v4
        with: { name: tfplan }
      - run: terraform apply tfplan
```

## Common Resource Patterns

### VPC Networking (AWS)

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-vpc"
  cidr = "10.0.0.0/16"

  azs              = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets   = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "prod"  # save cost in non-prod

  tags = local.common_tags
}
```

### IAM Role + Policy (least privilege)

```hcl
resource "aws_iam_role" "app_role" {
  name = "${local.name_prefix}-app"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "app_policy" {
  name = "app-policy"
  role = aws_iam_role.app_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.app_data.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.db_password.arn
      }
    ]
  })
}
```

### RDS Instance

```hcl
resource "aws_db_instance" "postgres" {
  identifier        = "${local.name_prefix}-postgres"
  engine            = "postgres"
  engine_version    = "16.2"
  instance_class    = var.db_instance_class
  allocated_storage = 100
  storage_encrypted = true

  db_name  = var.db_name
  username = "app"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = var.environment == "prod" ? 30 : 7
  deletion_protection     = var.environment == "prod"
  skip_final_snapshot     = var.environment != "prod"

  tags = local.common_tags
}
```

## Drift Detection and Import

### Detect Drift

```bash
terraform plan   # shows resources that diverged from state
```

Any `~` (update) or `-`/`+` (replace) on a resource you haven't changed = drift.

### Import Existing Resources

```bash
# Import by resource address and cloud ID
terraform import aws_s3_bucket.legacy my-existing-bucket

# After import, write matching HCL or Terraform will show a diff
```

### `moved` Block (safe refactoring)

```hcl
# Rename a resource without destroying it
moved {
  from = aws_s3_bucket.data
  to   = aws_s3_bucket.app_data
}
```

> See also: `ci-cd`, `containerization`, `security`

## Checklist

- [ ] Remote state backend configured (S3+DynamoDB or GCS) — state never committed to git
- [ ] State S3 bucket has versioning, encryption, and public access blocked
- [ ] All resources tagged with `environment`, `app`, and `managed_by = "terraform"`
- [ ] Infrastructure split into reusable modules with `variables.tf` and `outputs.tf`
- [ ] Modules pinned to specific versions (git tag or registry version constraint)
- [ ] `terraform plan -out=tfplan` used — apply from saved plan, not a re-plan
- [ ] Policy checks (OPA/Conftest) run on plan JSON before apply
- [ ] Production apply requires human approval (GitHub environment protection)
- [ ] IAM roles follow least privilege — no `"*"` actions or resources in policy
- [ ] Deletion protection enabled on RDS and other stateful prod resources
- [ ] `moved` blocks used for resource renames — never destroy-and-recreate
- [ ] `terraform plan` run after every manual change to detect drift
