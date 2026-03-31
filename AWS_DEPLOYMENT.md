# AWS Deployment Architecture & Cost Analysis

This document compares the current Railway/Cloudflare R2 deployment with an equivalent AWS deployment.

---

## Current Architecture (Railway + Cloudflare R2)

```
┌─────────────────────────────────────────────────────────────┐
│                         RAILWAY                              │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   FastAPI App       │    │   PostgreSQL                │ │
│  │   (Container)       │◄──►│   (Managed)                 │ │
│  │   512MB RAM         │    │   1GB Storage               │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE R2                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │   ito-uploads bucket                                    ││
│  │   - Shelf photos                                        ││
│  │   - Public CDN access                                   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Current Monthly Costs

| Service | Monthly Cost |
|---------|-------------|
| Railway Hobby Plan (compute) | $5/mo |
| Railway PostgreSQL | $0-5/mo (usage-based) |
| Cloudflare R2 (10GB free tier) | $0-3/mo |
| **Total** | **$5-15/mo** |

---

## AWS Architecture Options

### Option 1: Minimal (ECS Fargate + RDS)

Best for: Direct migration with minimal changes, serverless compute.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS VPC                                     │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Application Load Balancer                      │  │
│  │                    (HTTPS termination, routing)                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                   │                                      │
│                                   ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      ECS Fargate Service                          │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  FastAPI Container (0.25 vCPU, 512MB RAM)                   │  │  │
│  │  │  - Auto-scaling: 1-3 tasks                                  │  │  │
│  │  │  - OpenCV image processing                                  │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                   │                                      │
│                                   ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │               RDS PostgreSQL (db.t4g.micro)                       │  │
│  │               - 20GB gp3 storage                                  │  │
│  │               - Single AZ (dev) or Multi-AZ (prod)                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              S3 Bucket                                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │   ito-uploads                                                     │  │
│  │   - Shelf photos                                                  │  │
│  │   - CloudFront CDN (optional)                                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Option 1 Monthly Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|---------------|-------------|
| **ECS Fargate** | 0.25 vCPU, 512MB, 730 hrs | $8.50 |
| **Application Load Balancer** | 1 ALB + LCU usage | $18.00 |
| **RDS PostgreSQL** | db.t4g.micro, 20GB, Single-AZ | $13.50 |
| **S3 Storage** | 10GB + 10,000 requests | $0.50 |
| **ECR** | Container registry (1GB) | $0.10 |
| **Data Transfer** | 5GB egress | $0.45 |
| **CloudWatch** | Basic logs/metrics | $3.00 |
| **Total** | | **$44/mo** |

---

### Option 2: EC2-Based (Lower Cost)

Best for: Cost optimization, predictable workloads.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS VPC                                     │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                         EC2 Instance                              │  │
│  │                      (t4g.micro or t4g.small)                     │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  nginx (reverse proxy + SSL)                                │  │  │
│  │  │  ├── FastAPI (uvicorn)                                      │  │  │
│  │  │  └── PostgreSQL (local)                                     │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              S3 Bucket                                   │
│  ito-uploads (shelf photos)                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Option 2 Monthly Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|---------------|-------------|
| **EC2 t4g.micro** | 2 vCPU, 1GB RAM, 730 hrs (On-Demand) | $6.05 |
| **EBS Storage** | 20GB gp3 | $1.60 |
| **Elastic IP** | 1 static IP | $3.65 |
| **S3 Storage** | 10GB + 10,000 requests | $0.50 |
| **Data Transfer** | 5GB egress | $0.45 |
| **Total (On-Demand)** | | **$12.25/mo** |
| **Total (1-yr Reserved)** | 35% savings | **$8/mo** |
| **Total (Spot Instance)** | 70% savings | **$5/mo** |

**Note**: EC2-based removes managed DB redundancy. For production, add RDS (+$13.50/mo).

---

### Option 3: Serverless (Lambda + Aurora Serverless)

Best for: Variable/spiky traffic, pay-per-use model.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              API Gateway                                 │
│                    (HTTPS endpoints, throttling)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Lambda Functions                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐   │
│  │ api-handler   │  │ cv-processor  │  │ auth-handler              │   │
│  │ (FastAPI)     │  │ (OpenCV)      │  │ (JWT validation)          │   │
│  └───────────────┘  └───────────────┘  └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
              │                 │
              ▼                 ▼
┌─────────────────────┐  ┌─────────────────────────────────────────────────┐
│ Aurora Serverless   │  │                    S3 Bucket                    │
│ v2 (PostgreSQL)     │  │                  ito-uploads                    │
└─────────────────────┘  └─────────────────────────────────────────────────┘
```

#### Option 3 Monthly Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|---------------|-------------|
| **API Gateway** | 100K requests/mo | $3.50 |
| **Lambda** | 100K invocations, 1GB, 500ms avg | $2.10 |
| **Aurora Serverless v2** | 0.5 ACU minimum | $43.80 |
| **S3 Storage** | 10GB + 10,000 requests | $0.50 |
| **Data Transfer** | 5GB egress | $0.45 |
| **Total** | | **$50/mo** |

**Note**: Aurora Serverless has a high minimum cost. For low traffic, RDS is cheaper.

---

### Option 4: Production-Ready with ML (Future State)

Best for: YOLOv8 inference, high availability, enterprise-grade.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CloudFront (CDN + WAF)                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS VPC                                     │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                 Application Load Balancer                         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│         │                                        │                       │
│         ▼                                        ▼                       │
│  ┌─────────────────────┐              ┌─────────────────────────────┐   │
│  │  ECS Fargate        │              │  SageMaker Endpoint         │   │
│  │  (API Service)      │──inference──►│  (YOLOv8 model)             │   │
│  │  0.5 vCPU, 1GB      │              │  ml.g4dn.xlarge (GPU)       │   │
│  └─────────────────────┘              └─────────────────────────────┘   │
│         │                                                                │
│         ▼                                                                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │            RDS PostgreSQL (db.t4g.small, Multi-AZ)                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S3 (images)  │  CloudWatch (monitoring)  │  Secrets Manager (creds)    │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Option 4 Monthly Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|---------------|-------------|
| **CloudFront** | 50GB transfer, 100K requests | $5.00 |
| **ALB** | 1 ALB + LCU usage | $18.00 |
| **ECS Fargate** | 0.5 vCPU, 1GB, 730 hrs | $25.00 |
| **RDS PostgreSQL** | db.t4g.small, 50GB, Multi-AZ | $50.00 |
| **SageMaker Endpoint** | ml.g4dn.xlarge (GPU), 730 hrs | $570.00 |
| **S3 Storage** | 50GB + 50,000 requests | $2.00 |
| **Secrets Manager** | 3 secrets | $1.20 |
| **CloudWatch** | Logs, metrics, alarms | $10.00 |
| **Data Transfer** | 20GB egress | $1.80 |
| **Total** | | **$683/mo** |

**Cost Optimization for GPU**:
| Alternative | Monthly Cost |
|-------------|-------------|
| SageMaker Serverless Inference (pay-per-request) | $50-150/mo |
| Lambda + ONNX (CPU inference, no GPU) | $10-30/mo |
| Spot Instances for batch processing | $170/mo |

---

## Cost Comparison Summary

| Deployment | Monthly Cost | Best For |
|------------|-------------|----------|
| **Railway + R2 (Current)** | $5-15 | MVP, prototyping, small teams |
| **AWS Option 1: ECS + RDS** | $44 | Managed containers, auto-scaling |
| **AWS Option 2: EC2** | $8-12 | Cost-conscious, predictable load |
| **AWS Option 3: Serverless** | $50 | Variable traffic, hands-off ops |
| **AWS Option 4: Production ML** | $683 | GPU inference, enterprise SLAs |
| **AWS Option 4 (Optimized)** | $150-250 | GPU on-demand, batch inference |

---

## Annual Cost Projection

| Deployment | Year 1 | Year 2 | Year 3 |
|------------|--------|--------|--------|
| Railway + R2 | $180 | $180 | $180 |
| AWS EC2 (Reserved) | $96 | $96 | $96 |
| AWS ECS + RDS | $528 | $528 | $528 |
| AWS Production ML | $8,196 | $8,196 | $8,196 |
| AWS ML (Optimized) | $2,400 | $2,400 | $2,400 |

---

## Recommendation

### For Current MVP (5-10 merchandisers, OpenCV heuristics)

**Stay with Railway + Cloudflare R2** ($5-15/mo)

Reasons:
- Current traffic doesn't justify AWS complexity
- Railway provides automatic deployments from GitHub
- R2 has generous free tier and no egress fees
- OpenCV runs fine on shared compute

### When to Migrate to AWS

Migrate when ANY of these occur:

1. **Scale**: >50 concurrent users or >1000 visits/day
2. **ML Models**: Moving to YOLOv8 requiring GPU inference
3. **Compliance**: Need VPC isolation, HIPAA, SOC2
4. **SLA**: Require 99.9%+ uptime guarantees
5. **Integration**: Heavy use of other AWS services

### Recommended Migration Path

```
Phase 1 (Current): Railway + R2
    │ ($5-15/mo)
    │
    ▼ When traffic grows
Phase 2: AWS EC2 + S3
    │ ($12-25/mo)
    │
    ▼ When need auto-scaling
Phase 3: AWS ECS + RDS
    │ ($44-60/mo)
    │
    ▼ When deploying ML models
Phase 4: Full Production Stack
    ($150-683/mo depending on GPU usage)
```

---

## Quick Start: AWS EC2 Deployment

If you want to try AWS Option 2 (cheapest):

```bash
# 1. Launch EC2 instance
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \  # Ubuntu 22.04
  --instance-type t4g.micro \
  --key-name your-key \
  --security-groups ito-web-sg

# 2. SSH and install
ssh -i your-key.pem ubuntu@<instance-ip>
sudo apt update && sudo apt install -y docker.io docker-compose
git clone https://github.com/ElKuko/ITO-Project.git
cd ITO-Project

# 3. Create docker-compose.yml and deploy
docker-compose up -d

# 4. Set up SSL with Certbot
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d app.ito-pr.com
```

---

## Infrastructure as Code (Terraform Example)

For Option 1 (ECS + RDS), here's a starter Terraform config:

```hcl
# main.tf
provider "aws" {
  region = "us-east-1"
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0"

  name = "ito-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.20.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true  # Cost savings for dev
}

resource "aws_db_instance" "postgres" {
  identifier        = "ito-db"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t4g.micro"
  allocated_storage = 20

  db_name  = "ito"
  username = "ito_admin"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  skip_final_snapshot = true  # Set false for production
}

resource "aws_s3_bucket" "uploads" {
  bucket = "ito-uploads-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}
```

---

## Conclusion

| Metric | Railway + R2 | AWS (Comparable) |
|--------|-------------|------------------|
| Monthly Cost | $5-15 | $12-44 |
| Setup Complexity | Low | Medium-High |
| Auto-scaling | Basic | Advanced |
| GPU Support | No | Yes (SageMaker) |
| Compliance Options | Limited | Extensive |
| Vendor Lock-in | Low | Medium |

**Bottom line**: For an MVP serving 5-10 merchandisers in Puerto Rico, Railway remains the best choice. AWS becomes worthwhile when you need GPU inference, enterprise compliance, or significant scale.
