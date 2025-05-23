# UI Module

Core user interface components for authentication and user management.

## Current Structure

```
ui/
├── package.json        # Vue.js dependencies
├── vite.config.js      # Vite build configuration
├── index.html          # Main HTML template
├── src/
│   ├── main.js         # Vue app entry point
│   └── App.vue         # Main app component with auth
```

## Features

- User registration and login forms
- JWT token management
- Protected route handling
- User profile display
- Responsive design with clean styling

## Development

```bash
cd src/ts/role_play/ui
npm install
npm run dev  # Starts on http://localhost:3000
```

## API Integration

Connects to the Python backend at `http://localhost:8000`:
- POST `/auth/register` - User registration
- POST `/auth/login` - User authentication  
- GET `/auth/me` - Get current user profile