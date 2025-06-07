# Role Play System (RPS)

A scalable, multi-language role-playing conversation system built with FastAPI (Python) and Vue.js, designed for educational and training scenarios.

## Features

- **🎭 Interactive Role-Play Sessions**: Engage in structured conversations with AI-powered characters across various scenarios
- **🌐 Multi-Language Support**: Full internationalization with English and Traditional Chinese (zh-TW)
- **🔐 JWT Authentication**: Secure user authentication with role-based access control
- **☁️ Cloud-Ready**: Flexible storage backends (local file system, Google Cloud Storage, AWS S3)
- **🚀 Production-Ready**: Distributed locking, comprehensive logging, and monitoring
- **📊 Session Management**: Track, export, and evaluate conversation sessions
- **🎨 Modern UI**: Responsive Vue.js frontend with real-time updates

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (optional)
- Google Cloud SDK (for cloud deployment)

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/rps.git
cd rps

# Backend setup
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r src/python/requirements.txt

# Set environment variables
export JWT_SECRET_KEY="your-secret-key"
export STORAGE_PATH="./data"

# Run the backend server
python src/python/run_server.py

# In a new terminal - Frontend setup
cd src/ts/role_play/ui
npm install
npm run dev
```

Visit http://localhost:5173 for the UI and http://localhost:8000/docs for API documentation.

### Docker

```bash
# Build and run with Docker
make build-docker
make run-local-docker
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Vue.js    │────▶│  FastAPI    │────▶│  Storage    │
│  Frontend   │     │   Backend   │     │  Backend    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐      ┌─────────────┐
                    │     ADK     │      │     GCS     │
                    │   (Chat)    │      │  S3 / File  │
                    └─────────────┘      └─────────────┘
```

### Key Components

- **Frontend**: Vue.js 3 with TypeScript, Vue Router, and Vue i18n
- **Backend**: FastAPI with async support, Pydantic models, dependency injection
- **Storage**: Abstracted storage layer supporting local files, GCS, and S3
- **Authentication**: JWT-based auth with user roles (ADMIN, USER)
- **Chat Engine**: ADK (AI Development Kit) integration for role-play conversations
- **Locking**: Distributed locking strategies for concurrent access control

## Project Structure

```
rps/
├── src/
│   ├── python/             # Backend application
│   │   ├── role_play/      # Main application package
│   │   │   ├── chat/       # Chat functionality
│   │   │   ├── common/     # Shared utilities
│   │   │   ├── server/     # Server infrastructure
│   │   │   └── resources/  # Content files (scenarios)
│   │   └── run_server.py   # Application entry point
│   └── ts/                 # Frontend applications
│       └── role_play/ui/   # Vue.js application
├── config/                 # Environment configurations
│   ├── dev.yaml
│   ├── beta.yaml
│   └── prod.yaml
├── test/                   # Test suites
├── data/                   # Local storage (dev only)
└── Makefile               # Deployment automation
```

## API Overview

The system provides RESTful APIs for all operations:

- **Authentication**: `/api/auth/*` - User registration, login, profile management
- **Chat**: `/api/chat/*` - Session management, message handling, content delivery
- **Evaluation**: `/api/evaluation/*` - Session export and analysis

See [API.md](./API.md) for detailed endpoint documentation.

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ENV` | Environment (dev/beta/prod) | No | dev |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | Yes | - |
| `STORAGE_PATH` | Base path for file storage | Yes* | ./data |
| `STORAGE_TYPE` | Storage backend type | No | file |
| `GCS_BUCKET` | GCS bucket name | If GCS | - |
| `AWS_REGION` | AWS region | If S3 | - |
| `S3_BUCKET` | S3 bucket name | If S3 | - |

*Required for file storage type

### Storage Backends

The system supports multiple storage backends:

- **File Storage** (Development): Local file system storage
- **Google Cloud Storage** (Beta/Production): Scalable cloud storage
- **AWS S3** (Future): Alternative cloud storage option

Configure via `STORAGE_TYPE` environment variable.

## Deployment

### Cloud Deployment

```bash
# Deploy to beta environment
make deploy ENV=beta

# Deploy to production
make deploy ENV=prod
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

### Environment Configuration

- **Development**: Local file storage, debug enabled, relaxed security
- **Beta**: GCS storage, production-like settings, testing environment
- **Production**: GCS storage, strict security, monitoring enabled

See [ENVIRONMENTS.md](./ENVIRONMENTS.md) for environment details.

## Internationalization

The system supports multiple languages with:

- **Frontend**: Vue i18n with locale files
- **Backend**: Language-aware content loading
- **Content**: Separate scenario files per language

Currently supported languages:
- English (en) - Default
- Traditional Chinese (zh-TW)
- Japanese (ja) - Prepared for future

## Development

### Running Tests

```bash
# Run all tests
pytest test/python/

# Run with coverage
pytest test/python/ --cov=role_play --cov-report=html
```

### Code Style

- **Python**: Follow PEP 8, use type hints
- **TypeScript**: ESLint configuration provided
- **Commits**: Conventional commits recommended

### Adding New Features

1. Follow the modular architecture
2. Add tests for new functionality
3. Update API documentation
4. Consider internationalization

## Security

- JWT tokens for authentication
- Role-based access control (RBAC)
- CORS protection
- Input validation with Pydantic
- Secure storage of credentials

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) file for details.

## Support

For issues and feature requests, please use the GitHub issue tracker.

## Roadmap

- [ ] WebSocket support for real-time chat
- [ ] Audio streaming capabilities
- [ ] Enhanced evaluation tools
- [ ] Additional language support
- [ ] OAuth integration
- [ ] Mobile applications