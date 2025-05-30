# POC to Production Migration Guide

This guide outlines what needs to be cleaned up, refactored, or replaced when moving from the Proof of Concept (POC) to Beta/Production environments.

## 🚨 Critical Security Changes

### 1. **JWT Secret Management**
**POC**: JWT secret stored in environment variable
**Production**: 
- [ ] Migrate to Google Secret Manager with rotation policy
- [ ] Use different secrets for each environment
- [ ] Implement key rotation mechanism
- [ ] Use RS256 algorithm instead of HS256 for better security

```python
# TODO: Update config.py
jwt_algorithm: str = Field(default="RS256")  # Change from HS256
jwt_public_key_path: str = Field(...)
jwt_private_key_path: str = Field(...)
```

### 2. **CORS Configuration**
**POC**: Allows https://poc.rps.cattail-sw.com
**Production**:
- [ ] Restrict to exact production domains only
- [ ] Remove localhost origins
- [ ] Implement per-environment CORS policies
- [ ] Consider using API Gateway for CORS handling

```yaml
# config/prod.yaml
cors_origins:
  - "https://app.cattail-sw.com"  # Production domain only
enable_cors: true  # Or false if using API Gateway
```

### 3. **User Authentication**
**POC**: Basic JWT with email/password
**Production**:
- [ ] Implement OAuth 2.0 (Google, GitHub, etc.)
- [ ] Add Multi-Factor Authentication (MFA)
- [ ] Implement account lockout policies
- [ ] Add password complexity requirements
- [ ] Session management and forced logout

## 💾 Data Persistence Migration

### 1. **Storage Backend**
**POC**: Ephemeral FileStorage at `/tmp/data`
**Production**:
- [ ] Implement PostgreSQL for structured data
- [ ] Migrate to Google Cloud Storage for file storage
- [ ] Implement proper backup and recovery

```python
# TODO: Implement new storage backends
class PostgreSQLStorage(StorageBackend):
    """Production database storage."""
    pass

class GCSStorage(StorageBackend):
    """Google Cloud Storage for files."""
    pass
```

### 2. **Database Schema**
Create proper database migrations:
```sql
-- migrations/001_initial_schema.sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    scenario_id VARCHAR(100) NOT NULL,
    character_id VARCHAR(100) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    INDEX idx_user_sessions (user_id, started_at DESC)
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX idx_session_messages (session_id, created_at)
);
```

### 3. **Data Migration Strategy**
- [ ] Export POC data from JSONL files
- [ ] Transform to relational format
- [ ] Import into PostgreSQL
- [ ] Verify data integrity
- [ ] Archive POC data

## 🏗️ Infrastructure Changes

### 1. **Container Orchestration**
**POC**: Single Cloud Run service
**Production**:
- [ ] Kubernetes (GKE) for better control
- [ ] Implement horizontal pod autoscaling
- [ ] Set up node pools for different workloads
- [ ] Implement pod disruption budgets

### 2. **Service Architecture**
**POC**: Monolithic container
**Production**: Microservices
- [ ] Auth Service (separate deployment)
- [ ] Chat Service (with WebSocket support)
- [ ] Evaluation Service
- [ ] API Gateway (Kong or Apigee)

```yaml
# k8s/services/auth-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: auth
        image: gcr.io/project/auth-service:v1.0.0
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
```

### 3. **Load Balancing & CDN**
- [ ] Set up Cloud Load Balancer
- [ ] Configure Cloud CDN for static assets
- [ ] Implement health checks at multiple levels
- [ ] Set up SSL certificates with auto-renewal

## 📊 Monitoring & Observability

### 1. **Logging**
**POC**: Basic console logging
**Production**:
- [ ] Structured JSON logging
- [ ] Log aggregation with Cloud Logging
- [ ] Log retention policies
- [ ] Alert rules for errors

```python
# TODO: Implement structured logging
import structlog

logger = structlog.get_logger()
logger.info("user_action", 
    user_id=user.id, 
    action="chat_message",
    session_id=session_id,
    timestamp=datetime.utcnow().isoformat()
)
```

### 2. **Metrics & Tracing**
- [ ] Implement OpenTelemetry
- [ ] Set up Prometheus metrics
- [ ] Create Grafana dashboards
- [ ] Implement distributed tracing

```python
# TODO: Add metrics
from prometheus_client import Counter, Histogram

chat_messages_total = Counter('chat_messages_total', 'Total chat messages')
chat_response_time = Histogram('chat_response_seconds', 'Chat response time')
```

### 3. **Error Tracking**
- [ ] Integrate Sentry or similar
- [ ] Set up error budgets
- [ ] Implement proper error handling
- [ ] Create runbooks for common issues

## 🔧 Code Quality & Testing

### 1. **Environment Configuration**
**POC**: Single poc.yaml
**Production**:
- [ ] Separate configs for dev/staging/prod
- [ ] Use Helm charts for Kubernetes
- [ ] Implement feature flags
- [ ] Environment-specific secrets

```yaml
# config/prod.yaml
environment: "prod"
debug: false
log_level: "WARNING"
max_request_size: 10485760  # 10MB
request_timeout: 30
rate_limit_per_minute: 60
```

### 2. **Testing Strategy**
- [ ] Achieve >90% test coverage
- [ ] Add integration tests for all APIs
- [ ] Implement load testing
- [ ] Add security testing (OWASP)
- [ ] Continuous testing in CI/CD

### 3. **CI/CD Pipeline**
```yaml
# .github/workflows/production.yml
name: Production Deployment
on:
  push:
    tags:
      - 'v*'
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          make test
          make integration-test
          make security-scan
  
  build:
    needs: test
    steps:
      - name: Build and push
        run: |
          docker build -t $REGISTRY/$IMAGE:$TAG .
          docker push $REGISTRY/$IMAGE:$TAG
  
  deploy:
    needs: build
    environment: production
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl apply -f k8s/production/
          kubectl rollout status deployment/rps-backend
```

## 🚀 Performance Optimization

### 1. **Caching Strategy**
- [ ] Implement Redis for session cache
- [ ] Add response caching for scenarios
- [ ] Browser caching headers
- [ ] Database query caching

### 2. **API Optimization**
- [ ] Implement pagination for list endpoints
- [ ] Add field filtering
- [ ] Optimize database queries
- [ ] Implement connection pooling

### 3. **Frontend Optimization**
- [ ] Implement lazy loading
- [ ] Optimize bundle size
- [ ] Add Progressive Web App features
- [ ] Implement offline support

## 📝 Documentation & Compliance

### 1. **API Documentation**
- [ ] Complete OpenAPI/Swagger docs
- [ ] API versioning strategy
- [ ] Deprecation policies
- [ ] Client SDKs

### 2. **Operational Documentation**
- [ ] Runbooks for all services
- [ ] Disaster recovery procedures
- [ ] Security incident response plan
- [ ] Architecture decision records

### 3. **Compliance**
- [ ] GDPR compliance (if applicable)
- [ ] Data retention policies
- [ ] Privacy policy implementation
- [ ] Terms of service

## 🔐 Security Hardening

### 1. **Network Security**
- [ ] Implement VPC with private subnets
- [ ] Set up Cloud Armor (DDoS protection)
- [ ] Configure firewall rules
- [ ] Enable VPC Flow Logs

### 2. **Application Security**
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] CSRF tokens
- [ ] Rate limiting per user/IP

### 3. **Secrets Management**
```python
# TODO: Implement proper secrets management
from google.cloud import secretmanager

def get_secret(secret_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
```

## 📅 Migration Timeline

### Phase 1: Foundation (Week 1-2)
- [ ] Set up production GCP project
- [ ] Configure networking (VPC, subnets)
- [ ] Set up GKE cluster
- [ ] Configure Secret Manager

### Phase 2: Data Layer (Week 3-4)
- [ ] Provision Cloud SQL (PostgreSQL)
- [ ] Create database schema
- [ ] Migrate POC data
- [ ] Set up backup procedures

### Phase 3: Services (Week 5-6)
- [ ] Split monolith into microservices
- [ ] Deploy services to GKE
- [ ] Set up service mesh (Istio)
- [ ] Configure load balancing

### Phase 4: Observability (Week 7-8)
- [ ] Implement logging pipeline
- [ ] Set up monitoring dashboards
- [ ] Configure alerts
- [ ] Load testing

### Phase 5: Security & Polish (Week 9-10)
- [ ] Security audit
- [ ] Performance optimization
- [ ] Documentation
- [ ] Training and handover

## 🎯 Success Criteria

Before considering the migration complete:
- [ ] All tests passing (>90% coverage)
- [ ] Load test passing (1000 concurrent users)
- [ ] Security scan clean
- [ ] Zero data loss during migration
- [ ] Monitoring dashboards operational
- [ ] Disaster recovery tested
- [ ] Documentation complete
- [ ] Team trained on new infrastructure

## 🛠️ Cleanup Checklist

### Remove POC-specific code:
- [ ] Remove test JWT secrets from code
- [ ] Remove localhost from CORS origins
- [ ] Remove debug logging
- [ ] Remove POC environment configs
- [ ] Clean up test data

### Update configurations:
- [ ] Update all environment variables
- [ ] Update DNS records
- [ ] Update SSL certificates
- [ ] Update API endpoints
- [ ] Update documentation

This migration guide ensures a smooth transition from POC to production while maintaining security, scalability, and reliability.
